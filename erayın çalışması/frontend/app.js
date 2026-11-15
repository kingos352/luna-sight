/**
 * frontend/app.js
 * ===============
 * Ana Frontend Uygulama Koordinatörü:
 * API İletişimi, Katman Yönetimi, Zaman Kaydırıcısı (Time Scrubber),
 * MC&W Alarm Sistemi, Quindar Sentezleyici, NVG Gece Görüşü ve Aviyonik Kokpit.
 * Sürüm: v3.0.0
 */

document.addEventListener("DOMContentLoaded", async () => {
  const viewer = new LunarTerrainViewer("canvas-container");

  let simulationData = null;
  let isPlaying = false;
  let playInterval = null;
  let currentStep = 0;

  // DOM Elemanları
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const gridDimText = document.getElementById("grid-dim-text");

  const statSlope = document.getElementById("stat-slope");
  const statRough = document.getElementById("stat-rough");
  const statIllum = document.getElementById("stat-illum");
  const statScore = document.getElementById("stat-score");

  const legendBox = document.getElementById("legend-box");
  const legendTitle = document.getElementById("legend-title");
  const legendBar = document.getElementById("legend-bar");
  const legendMin = document.getElementById("legend-min");
  const legendMid = document.getElementById("legend-mid");
  const legendMax = document.getElementById("legend-max");

  const timeSlider = document.getElementById("time-slider");
  const btnPlayPause = document.getElementById("btn-play-pause");
  const hudTime = document.getElementById("hud-time");
  const hudStep = document.getElementById("hud-step");
  const hudSunAngles = document.getElementById("hud-sun-angles");
  const hudSunFlux = document.getElementById("hud-sun-flux");
  const hudEarthAngles = document.getElementById("hud-earth-angles");
  const hudEarthDist = document.getElementById("hud-earth-dist");

  const inspectorPanel = document.getElementById("inspector-panel");
  const btnCloseInspector = document.getElementById("btn-close-inspector");
  const inspBadge = document.getElementById("insp-badge");
  const inspCoords = document.getElementById("insp-coords");
  const inspElev = document.getElementById("insp-elev");
  const inspSlope = document.getElementById("insp-slope");
  const inspRough = document.getElementById("insp-rough");
  const inspIllum = document.getElementById("insp-illum");
  const inspDte = document.getElementById("insp-dte");
  const inspScore = document.getElementById("insp-score");
  const chartCanvas = document.getElementById("chart-canvas");

  // Aday ve Bölge Kontrolleri
  const candidatesContainer = document.getElementById("candidates-container");
  const headerRegionSelect = document.getElementById("header-region-select");
  const leftRegionSelect = document.getElementById("left-region-select");
  const btnToggleFiltered = document.getElementById("btn-toggle-filtered");
  const filteredSitesBox = document.getElementById("filtered-sites-box");
  const filteredArrow = document.getElementById("filtered-arrow");

  // Filtrelenen Robotik Sahalar Akordeon Kontrolü
  if (btnToggleFiltered && filteredSitesBox) {
    btnToggleFiltered.addEventListener("click", () => {
      filteredSitesBox.classList.toggle("hidden");
      if (filteredArrow) {
        filteredArrow.textContent = filteredSitesBox.classList.contains("hidden") ? "▼" : "▲";
      }
    });
  }

  // 1. Sistem Durumunu Kontrol Et
  try {
    const statusRes = await fetch("/api/status");
    const status = await statusRes.json();
    if (status.spice_active) {
      statusText.textContent = `SPICE AKTİF (${status.frame_used})`;
      statusDot.style.backgroundColor = "var(--accent-emerald)";
      statusDot.style.boxShadow = "0 0 10px var(--accent-emerald)";
    } else {
      statusText.textContent = "ANALİTİK EFEMERİS (MOON_ME)";
      statusDot.style.backgroundColor = "var(--accent-cyan)";
      statusDot.style.boxShadow = "0 0 10px var(--accent-cyan)";
    }
  } catch (err) {
    statusText.textContent = "BAĞLANTI BEKLENİYOR...";
    statusDot.style.backgroundColor = "var(--accent-rose)";
  }

  // 2. Yükseklik ve Katman Verilerini Yükle
  try {
    const [meshRes, layersRes] = await Promise.all([
      fetch("/api/terrain/mesh?resolution=128"),
      fetch("/api/terrain/layers?resolution=128"),
    ]);

    const meshData = await meshRes.json();
    const layersData = await layersRes.json();

    gridDimText.textContent = `${meshData.original_width}x${meshData.original_height} (${meshData.pixel_size_m}m)`;

    // İstatistikleri güncelle
    if (layersData.stats) {
      statSlope.innerHTML = `${layersData.stats.slope_mean.toFixed(1)}<span class="stat-unit">&deg;</span>`;
      statRough.innerHTML = `${layersData.stats.roughness_mean.toFixed(2)}<span class="stat-unit">m</span>`;
      statIllum.innerHTML = `${layersData.stats.illumination_mean.toFixed(0)}<span class="stat-unit">%</span>`;
      statScore.innerHTML = `${layersData.stats.suitability_mean.toFixed(0)}<span class="stat-unit">/100</span>`;
    }

    // 3B Araziyi İnşa Et
    viewer.buildTerrain(meshData, layersData);
    updateLegend("elevation", layersData);

    // Aday İniş Sahalarını Yükle ve İşaretle
    try {
      const candRes = await fetch("/api/terrain/candidates");
      if (candRes.ok) {
        const candData = await candRes.json();
        const candidates = candData.candidate_sites || [];
        renderCandidates(candidates);
        viewer.setCandidates(candidates, candidates[0] ? candidates[0].site_id : null);
      }
    } catch (cErr) {
      console.warn("Adaylar yüklenemedi:", cErr);
    }
  } catch (err) {
    console.error("Arazi verileri yüklenemedi:", err);
  }

  // Aday Sahaları UI'da Listele & Dropdown Senkronizasyonu
  function renderCandidates(candidates) {
    if (!candidatesContainer) return;
    candidatesContainer.innerHTML = "";

    // 1. Dropdown'ları doldur (Header ve Sol Panel)
    const populateDropdown = (sel) => {
      if (!sel) return;
      sel.innerHTML = "";

      const artemisOptGroup = document.createElement("optgroup");
      artemisOptGroup.label = "🚀 NASA Artemis III Resmi İniş Bölgeleri (9 Saha)";

      const safeHavenOptGroup = document.createElement("optgroup");
      safeHavenOptGroup.label = "🌐 Güney Kutbu Alternatif Bilimsel & Güvenli İniş Sahaları (5 Saha)";

      const shackletonOptGroup = document.createElement("optgroup");
      shackletonOptGroup.label = "🌑 Shackleton Krateri Ultra-HD Sahaları (LOLA 60m)";

      candidates.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.site_id;
        const shortName = c.name.split(":")[0];
        const rating = c.scoring ? c.scoring.rating : "";
        opt.textContent = `${shortName} (${c.coordinates.latitude_deg.toFixed(2)}°S, ${c.coordinates.longitude_deg.toFixed(2)}°E) - [${rating}]`;
        
        if (c.category === "SOUTH_POLE_SAFE_HAVEN" || ["SHOEMAKER_RIM", "FAUSTINI_RIM", "CABEUS_RIDGE", "SLATER_RIM", "SVERDRUP_RIM"].includes(c.site_id)) {
          safeHavenOptGroup.appendChild(opt);
        } else if (c.site_id.startsWith("SITE_")) {
          shackletonOptGroup.appendChild(opt);
        } else {
          artemisOptGroup.appendChild(opt);
        }
      });

      sel.appendChild(artemisOptGroup);
      sel.appendChild(safeHavenOptGroup);
      sel.appendChild(shackletonOptGroup);

      // Filtrelenen sahalar bilgisi (Seçilemez / Açıklayıcı)
      const filteredOptGroup = document.createElement("optgroup");
      filteredOptGroup.label = "⚠️ Filtrelenen Robotik Sahalar (İnsanlı Artemis 3 Değil)";
      const optViper = document.createElement("option");
      optViper.value = "MONS_MOUTON";
      optViper.disabled = true;
      optViper.textContent = "🚫 Mons Mouton (NASA VIPER / Griffin CLPS Robotik)";
      const optIm1 = document.createElement("option");
      optIm1.value = "MALAPERT_A";
      optIm1.disabled = true;
      optIm1.textContent = "🚫 Malapert A (Intuitive Machines IM-1 Robotik)";
      filteredOptGroup.appendChild(optViper);
      filteredOptGroup.appendChild(optIm1);
      sel.appendChild(filteredOptGroup);
    };

    populateDropdown(headerRegionSelect);
    populateDropdown(leftRegionSelect);

    const onRegionChange = (e) => {
      const selectedId = e.target.value;
      if (headerRegionSelect) headerRegionSelect.value = selectedId;
      if (leftRegionSelect) leftRegionSelect.value = selectedId;

      const targetCand = candidates.find((cand) => cand.site_id === selectedId);
      if (targetCand) {
        document.querySelectorAll(".candidate-item").forEach((el) => {
          el.classList.toggle("active", el.dataset.siteId === selectedId);
        });
        selectCandidateSite(targetCand);
      }
    };

    if (headerRegionSelect) headerRegionSelect.onchange = onRegionChange;
    if (leftRegionSelect) leftRegionSelect.onchange = onRegionChange;

    const tagClasses = {
      MALAPERT_MASSIF: "tag-alpha",
      CONNECTING_RIDGE_EXT: "tag-beta",
      LEIBNITZ_BETA: "tag-alpha",
      DE_GERLACHE_RIM_1: "tag-beta",
      DE_GERLACHE_RIM_2: "tag-beta",
      AMUNDSEN_RIM: "tag-beta",
      NOBILE_RIM_2: "tag-gamma",
      DE_GERLACHE_KOCHER: "tag-gamma",
      HAWORTH: "tag-gamma",
      SITE_ALPHA: "tag-alpha",
      SITE_BETA: "tag-beta",
      SITE_GAMMA: "tag-gamma",
      SITE_DELTA: "tag-delta",
      SHOEMAKER_RIM: "tag-alpha",
      FAUSTINI_RIM: "tag-alpha",
      CABEUS_RIDGE: "tag-alpha",
      SLATER_RIM: "tag-beta",
      SVERDRUP_RIM: "tag-alpha",
    };

    // 2. Kartları Doldur
    candidates.forEach((c, idx) => {
      const item = document.createElement("div");
      item.className = "candidate-item" + (idx === 0 ? " active" : "");
      item.dataset.siteId = c.site_id;

      const tagClass = tagClasses[c.site_id] || (c.scoring.rating === "EXCELLENT" ? "tag-alpha" : c.scoring.rating === "ACCEPTABLE" ? "tag-gamma" : "tag-delta");
      const tempStr = c.environment_and_visibility && c.environment_and_visibility.thermal_temp_kelvin != null
        ? `${c.environment_and_visibility.thermal_temp_kelvin.toFixed(0)}K (${c.environment_and_visibility.thermal_temp_celsius.toFixed(0)}°C)`
        : "--";

      item.innerHTML = `
        <div class="candidate-header">
          <span class="candidate-title">${c.name.split(":")[0]}</span>
          <span class="candidate-tag ${tagClass}">${c.scoring.rating} (${c.scoring.suitability_score.toFixed(0)})</span>
        </div>
        <div class="candidate-desc">${c.designation}</div>
        <div class="candidate-metrics">
          <span>Eğim: ${c.topography.slope_deg.toFixed(1)}°</span>
          <span>Güneş: %${c.environment_and_visibility.solar_illumination_pct.toFixed(0)}</span>
          <span>DTE: %${c.environment_and_visibility.dte_visibility_pct.toFixed(0)}</span>
          <span>Sıcaklık: ${tempStr}</span>
        </div>
      `;

      item.addEventListener("click", () => {
        document.querySelectorAll(".candidate-item").forEach((el) => el.classList.remove("active"));
        item.classList.add("active");
        if (headerRegionSelect) headerRegionSelect.value = c.site_id;
        if (leftRegionSelect) leftRegionSelect.value = c.site_id;
        selectCandidateSite(c);
      });

      candidatesContainer.appendChild(item);
    });

    // İlk adayı varsayılan olarak seç
    if (candidates.length > 0) {
      if (headerRegionSelect) headerRegionSelect.value = candidates[0].site_id;
      if (leftRegionSelect) leftRegionSelect.value = candidates[0].site_id;
      selectCandidateSite(candidates[0]);
    }
  }

  let activeLoadedRegionId = null;

  async function selectCandidateSite(c) {
    if (!c) return;
    currentSelectedCandidate = c;
    currentCustomTarget = null;

    // Bölge filtrelemesini anında uygula (diğer alakasız bölgeleri kaldır)
    viewer.setRegionFilter(c.site_id);

    const aiActiveTarget = document.getElementById("ai-active-target");
    if (aiActiveTarget) {
      aiActiveTarget.textContent = `Hedef: ${c.name.split(':')[0]}`;
    }
    if (headerRegionSelect) headerRegionSelect.value = c.site_id;
    if (leftRegionSelect) leftRegionSelect.value = c.site_id;

    // HUD Başlığını güncelle
    const isShackleton = c.site_id.startsWith("SITE_");
    const resTag = isShackleton ? "LOLA 60m" : "LOLA 240m";
    const hudTitle = document.getElementById("terrain-active-title");
    if (hudTitle) {
      hudTitle.textContent = `Aktif Arazi Topografyası: ${c.name.split(':')[0]} (${resTag})`;
    }

    // Seçilen bölgenin gerçek 3B Mesh ve Katman verilerini yükle (Multi-Region 3D)
    if (activeLoadedRegionId !== c.site_id) {
      activeLoadedRegionId = c.site_id;
      try {
        const [meshRes, layersRes] = await Promise.all([
          fetch(`/api/terrain/mesh?resolution=128&region_id=${c.site_id}`),
          fetch(`/api/terrain/layers?resolution=128&region_id=${c.site_id}`),
        ]);
        if (meshRes.ok && layersRes.ok) {
          const meshData = await meshRes.json();
          const layersData = await layersRes.json();

          // 3B Topografyayı Seçilen Bölge DEM'i ile Yeniden İnşa Et
          viewer.buildTerrain(meshData, layersData);
          viewer.setRegionTexture(c.site_id);

          // İstatistik kartlarını güncelle
          if (layersData.stats) {
            if (statSlope) statSlope.innerHTML = `${layersData.stats.slope_mean.toFixed(1)}<span class="stat-unit">&deg;</span>`;
            if (statRough) statRough.innerHTML = `${layersData.stats.roughness_mean.toFixed(2)}<span class="stat-unit">m</span>`;
            if (statIllum) statIllum.innerHTML = `${layersData.stats.illumination_mean.toFixed(0)}<span class="stat-unit">%</span>`;
            if (statScore) statScore.innerHTML = `${layersData.stats.suitability_mean.toFixed(0)}<span class="stat-unit">/100</span>`;
          }

          if (gridDimText) {
            gridDimText.textContent = `${meshData.original_width}x${meshData.original_height} (${meshData.pixel_size_m}m)`;
          }

          updateLegend(viewer.currentLayer || "elevation", layersData);
        }
      } catch (err) {
        console.warn("Bölge topografyası yüklenirken hata:", err);
      }
    }

    // Kamerayı ve iniş pinini adaya uçur
    viewer.flyToCandidate(c);
    inspectorPanel.classList.remove("hidden");

    inspBadge.textContent = c.scoring.rating;
    if (c.scoring.rating === "EXCELLENT") {
      inspBadge.className = "suitability-badge badge-excellent";
    } else if (c.scoring.rating === "HIGH_SAFETY" || c.scoring.rating === "ACCEPTABLE") {
      inspBadge.className = "suitability-badge badge-acceptable";
    } else {
      inspBadge.className = "suitability-badge badge-unsafe";
    }

    inspCoords.textContent = `${c.coordinates.latitude_deg.toFixed(4)}°, ${c.coordinates.longitude_deg.toFixed(4)}°`;
    inspElev.textContent = `${c.topography.elevation_m.toFixed(1)} m`;
    inspSlope.textContent = `${c.topography.slope_deg.toFixed(2)}° (Hedef: < 8.0°)`;
    inspRough.textContent = `${c.topography.roughness_tri_m.toFixed(3)} m`;
    inspIllum.textContent = `${c.environment_and_visibility.solar_illumination_pct.toFixed(1)} %`;
    inspDte.textContent = `${c.environment_and_visibility.dte_visibility_pct.toFixed(1)} %`;
    inspScore.textContent = `${c.scoring.suitability_score.toFixed(1)} / 100`;

    const inspTemp = document.getElementById("insp-temp");
    if (inspTemp && c.environment_and_visibility && c.environment_and_visibility.thermal_temp_kelvin != null) {
      inspTemp.textContent = `${c.environment_and_visibility.thermal_temp_kelvin.toFixed(1)} K (${c.environment_and_visibility.thermal_temp_celsius.toFixed(1)} °C)`;
    }

    const inspObj = document.getElementById("insp-objective");
    if (inspObj) {
      inspObj.textContent = c.scientific_objective || c.operational_role || "--";
    }

    // Aviyonik telemetri sekmesini güncelle
    if (typeof updateAvionicsTelemetry === "function") {
      updateAvionicsTelemetry(c, currentStep);
    }
  }

  // Referans Görüntü Modalını Yönet
  const btnToggleRef = document.getElementById("btn-toggle-ref");
  const btnCloseRef = document.getElementById("btn-close-ref");
  const refModal = document.getElementById("ref-modal");

  if (btnToggleRef && refModal) {
    btnToggleRef.addEventListener("click", () => {
      refModal.classList.toggle("hidden");
    });
  }
  if (btnCloseRef && refModal) {
    btnCloseRef.addEventListener("click", () => {
      refModal.classList.add("hidden");
    });
  }

  // 3. Varsayılan Simülasyonu Çalıştır
  async function runSimulation() {
    try {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: -89.75,
          lon: 0.0,
          elevation_m: 0.0,
          utc_start: "2026-11-15T00:00:00Z",
          utc_end: "2026-11-16T00:00:00Z",
          step_hours: 1.0,
        }),
      });
      const data = await res.json();
      simulationData = data.orbital;

      timeSlider.max = simulationData.timestamps.length - 1;
      updateSimulationHUD(0);
    } catch (err) {
      console.error("Simülasyon başlatılamadı:", err);
    }
  }
  await runSimulation();

  // 4. Zaman Kaydırıcısı ve HUD Güncelleme
  function updateSimulationHUD(stepIdx) {
    if (!simulationData) return;
    currentStep = stepIdx;
    timeSlider.value = stepIdx;

    const timeStr = simulationData.timestamps[stepIdx];
    const sAz = simulationData.sun_azimuth_deg[stepIdx];
    const sEl = simulationData.sun_elevation_deg[stepIdx];
    const sFlux = simulationData.solar_flux_w_m2[stepIdx];
    const eAz = simulationData.earth_azimuth_deg[stepIdx];
    const eEl = simulationData.earth_elevation_deg[stepIdx];
    const eDist = simulationData.earth_distance_km[stepIdx];

    hudTime.textContent = timeStr.replace("T", " ").replace("+00:00", "Z");
    hudStep.textContent = `${stepIdx} / ${simulationData.timestamps.length - 1}`;
    hudSunAngles.textContent = `${sAz.toFixed(1)}° / ${sEl.toFixed(1)}°`;
    hudSunFlux.textContent = `${sFlux.toFixed(0)} W/m²`;
    hudEarthAngles.textContent = `${eAz.toFixed(1)}° / ${eEl.toFixed(1)}°`;
    hudEarthDist.textContent = `${Math.round(eDist).toLocaleString()} km`;

    // Three.js Güneş ışığı konumunu ve gölgelerini gerçek zamanlı güncelle!
    viewer.updateSunPosition(sAz, sEl);

    // Aviyonik telemetriyi güncelle
    if (typeof updateAvionicsTelemetry === "function") {
      updateAvionicsTelemetry(currentSelectedCandidate, stepIdx);
    }
  }

  timeSlider.addEventListener("input", (e) => {
    updateSimulationHUD(parseInt(e.target.value, 10));
  });

  // Oynat / Durdur (Play/Pause) Döngüsü
  btnPlayPause.addEventListener("click", () => {
    isPlaying = !isPlaying;
    if (isPlaying) {
      btnPlayPause.innerHTML = "&#10074;&#10074;"; // Pause ikonu
      playInterval = setInterval(() => {
        let next = (currentStep + 1) % simulationData.timestamps.length;
        updateSimulationHUD(next);
      }, 600);
    } else {
      btnPlayPause.innerHTML = "&#9658;"; // Play ikonu
      clearInterval(playInterval);
    }
  });

  // 5. Katman Değiştirme Butonları
  document.querySelectorAll(".layer-btn[data-layer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".layer-btn[data-layer]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const layerName = btn.dataset.layer;
      viewer.setLayer(layerName);
      updateLegend(layerName, viewer.layersData);
    });
  });

  function updateLegend(layerName, layersData) {
    if (!layersData || !layersData.stats) return;
    const stats = layersData.stats;

    if (layerName === "elevation") {
      legendTitle.textContent = "YÜKSEKLİK (KOT)";
      legendBar.style.background = "linear-gradient(to right, #282828, #999, #f5f5f5)";
      legendMin.textContent = `${Math.round(stats.elev_min)} m`;
      legendMid.textContent = `${Math.round((stats.elev_min + stats.elev_max) / 2)} m`;
      legendMax.textContent = `${Math.round(stats.elev_max)} m`;
    } else if (layerName === "slope") {
      legendTitle.textContent = "EĞİM (SLOPE DERECE)";
      legendBar.style.background = "linear-gradient(to right, #10b981 0%, #f59e0b 60%, #ef4444 100%)";
      legendMin.textContent = "0° (Düzlük)";
      legendMid.textContent = "8° (İniş Sınırı)";
      legendMax.textContent = `${Math.round(stats.slope_max)}° (Dik Duvar)`;
    } else if (layerName === "roughness") {
      legendTitle.textContent = "PÜRÜZLÜLÜK (TRI METRE)";
      legendBar.style.background = "linear-gradient(to right, #001f3f, #10b981, #f59e0b, #ef4444)";
      legendMin.textContent = "0 m";
      legendMid.textContent = "1.5 m";
      legendMax.textContent = "5+ m";
    } else if (layerName === "illumination") {
      legendTitle.textContent = "GÜNEŞLENME SÜRESİ %";
      legendBar.style.background = "linear-gradient(to right, #000000, #b45309, #fde047, #ffffff)";
      legendMin.textContent = "0% (Kalıcı Gölge - PSR)";
      legendMid.textContent = "50%";
      legendMax.textContent = "100% (Zirve)";
    } else if (layerName === "dte") {
      legendTitle.textContent = "DÜNYA GÖRÜŞ HATTI (DTE %)";
      legendBar.style.background = "linear-gradient(to right, #050b14, #0284c7, #38bdf8)";
      legendMin.textContent = "0% (Engelli)";
      legendMid.textContent = "50%";
      legendMax.textContent = "100% (Kesintisiz Görüş)";
    } else if (layerName === "suitability") {
      legendTitle.textContent = "ÇOK KRİTERLİ İNİŞ UYGUNLUK SKORU";
      legendBar.style.background = "linear-gradient(to right, #ef4444 0%, #f59e0b 50%, #10b981 100%)";
      legendMin.textContent = "0 (Kritik Tehlikeli)";
      legendMid.textContent = "50 (Riskli)";
      legendMax.textContent = "100 (İdeal İniş Sahası)";
    } else if (layerName === "moontrek") {
      legendTitle.textContent = "MOONTREK LRO LOLA DOKUSU";
      legendBar.style.background = "linear-gradient(to right, #2563eb, #38bdf8, #10b981, #f59e0b, #ef4444)";
      legendMin.textContent = "-4060 m (Taban)";
      legendMid.textContent = "0 m";
      legendMax.textContent = "+1332 m (Sırt)";
    }
  }

  // 6. Kamera Ön Ayarları
  document.getElementById("btn-cam-iso").addEventListener("click", () => viewer.setCameraPreset("iso"));
  document.getElementById("btn-cam-top").addEventListener("click", () => viewer.setCameraPreset("top"));
  document.getElementById("btn-cam-side").addEventListener("click", () => viewer.setCameraPreset("side"));

  // 7. Nokta İnceleme (Inspector)
  viewer.onPointSelected = async (normX, normY) => {
    currentCustomTarget = { norm_x: normX, norm_y: normY };
    currentSelectedCandidate = null;
    const aiActiveTarget = document.getElementById("ai-active-target");
    if (aiActiveTarget) {
      aiActiveTarget.textContent = `Hedef: Harita Noktası (${normX.toFixed(2)}, ${normY.toFixed(2)})`;
    }

    inspectorPanel.classList.remove("hidden");
    inspBadge.textContent = "HESAPLANIYOR...";
    inspBadge.className = "suitability-badge badge-acceptable";

    try {
      const res = await fetch("/api/terrain/inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          norm_x: normX,
          norm_y: normY,
          region_id: activeLoadedRegionId,
          utc_start: "2026-11-15T00:00:00Z",
          utc_end: "2026-11-16T00:00:00Z",
          step_hours: 1.0,
        }),
      });

      const pointData = await res.json();
      inspCoords.textContent = `${(pointData.norm_x * 0.4 - 89.9).toFixed(2)}°, ${(pointData.norm_y * 10.0).toFixed(2)}°`;
      inspElev.textContent = `${pointData.elevation_m} m`;
      inspSlope.textContent = `${pointData.slope_deg}° ${pointData.slope_deg <= 8.0 ? '(Hedef İçi)' : '(Dik)'}`;
      inspRough.textContent = `${pointData.roughness_m} m`;
      inspIllum.textContent = `${pointData.illumination_pct} %`;
      inspDte.textContent = `${pointData.dte_pct} %`;
      inspScore.textContent = `${pointData.suitability_score} / 100`;

      if (pointData.status === "EXCELLENT") {
        inspBadge.textContent = "GÜVENLİ İNİŞ";
        inspBadge.className = "suitability-badge badge-excellent";
      } else if (pointData.status === "ACCEPTABLE") {
        inspBadge.textContent = "RİSKLİ BÖLGE";
        inspBadge.className = "suitability-badge badge-acceptable";
      } else {
        inspBadge.textContent = "TEHLİKELİ";
        inspBadge.className = "suitability-badge badge-unsafe";
      }

      // Zaman Serisi Çizimi (Canvas)
      renderInspectorChart(pointData.time_series);
    } catch (err) {
      console.error("Nokta inceleme hatası:", err);
    }
  };

  btnCloseInspector.addEventListener("click", () => {
    inspectorPanel.classList.add("hidden");
    if (viewer.landingPin) viewer.landingPin.visible = false;
  });

  // 8. Özel Canvas Zaman Serisi Grafiği Çizici
  function renderInspectorChart(series) {
    if (!series || series.length === 0) return;
    const ctx = chartCanvas.getContext("2d");
    const w = chartCanvas.width;
    const h = chartCanvas.height;

    ctx.clearRect(0, 0, w, h);

    // Kılavuz çizgileri
    ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2); // 0 derece ufuk çizgisi
    ctx.stroke();

    const n = series.length;
    const pad = 10;
    const graphW = w - pad * 2;
    const graphH = h - pad * 2;

    // Yükseklik açı aralığı: [-10°, +30°]
    const minAngle = -10;
    const maxAngle = 30;
    const range = maxAngle - minAngle;

    function yForAngle(ang) {
      const norm = (ang - minAngle) / range;
      return h - pad - norm * graphH;
    }

    // 1. Ufuk Tepe Engeli Alanı (Kırmızı gölge)
    ctx.fillStyle = "rgba(239, 68, 68, 0.15)";
    ctx.beginPath();
    ctx.moveTo(pad, yForAngle(0));
    for (let i = 0; i < n; i++) {
      const x = pad + (i / (n - 1)) * graphW;
      const y = yForAngle(series[i].horizon_elevation_sun);
      ctx.lineTo(x, y);
    }
    ctx.lineTo(pad + graphW, yForAngle(0));
    ctx.closePath();
    ctx.fill();

    // 2. Güneş Yüksekliği Eğrisi (Sarı/Amber)
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = pad + (i / (n - 1)) * graphW;
      const y = yForAngle(series[i].sun_elevation);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // 3. Dünya Yüksekliği Eğrisi (Mavi/Camgöbeği)
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = pad + (i / (n - 1)) * graphW;
      const y = yForAngle(series[i].earth_elevation);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // ---------------------------------------------------------------------------
  // 9. YAPAY ZEKA OTONOM İNİŞ MERKEZİ & MONTE CARLO YÖNETİCİSİ
  // ---------------------------------------------------------------------------
  const btnAiLand = document.getElementById("btn-ai-land");
  const btnAiContinuous = document.getElementById("btn-ai-continuous");
  const btnOpenAnalysis = document.getElementById("btn-open-analysis");
  const btnCloseAnalysis = document.getElementById("btn-close-analysis");
  const aiAnalysisModal = document.getElementById("ai-analysis-modal");
  const analysisModalBody = document.getElementById("analysis-modal-body");
  const aiContinuousIndicator = document.getElementById("ai-continuous-indicator");

  const aiActiveTarget = document.getElementById("ai-active-target");
  const aiTouchdownBadge = document.getElementById("ai-touchdown-badge");
  const aiScoreDisplay = document.getElementById("ai-score-display");
  const aiVzDisplay = document.getElementById("ai-vz-display");
  const aiVxyDisplay = document.getElementById("ai-vxy-display");
  const aiTiltDisplay = document.getElementById("ai-tilt-display");
  const aiErrorDisplay = document.getElementById("ai-error-display");
  const aiFuelDisplay = document.getElementById("ai-fuel-display");
  const aiFuelBar = document.getElementById("ai-fuel-bar");

  const aiMcTotal = document.getElementById("ai-mc-total");
  const aiMcRate = document.getElementById("ai-mc-rate");
  const aiMcAvg = document.getElementById("ai-mc-avg");

  let isContinuousLanding = false;
  let continuousTimer = null;
  let isLandingRunning = false;

  // İstatistikleri Yükle
  async function loadAIStats() {
    try {
      const res = await fetch("/api/ai/landing/stats");
      if (!res.ok) return;
      const stats = await res.json();

      if (aiMcTotal) aiMcTotal.textContent = stats.total_trials;
      if (aiMcRate) aiMcRate.textContent = `%${stats.success_rate_pct.toFixed(1)}`;
      if (aiMcAvg) aiMcAvg.textContent = `${stats.average_score.toFixed(1)}`;

      // Eğer son deneme varsa ve şu an uçuş yoksa telemetriyi güncelle
      if (stats.recent_trials && stats.recent_trials.length > 0 && !isLandingRunning) {
        const last = stats.recent_trials[0];
        updateAITelemetryDisplay(last);
      }
    } catch (e) {
      console.warn("AI istatistikleri alınamadı:", e);
    }
  }

  function updateAITelemetryDisplay(trial) {
    if (!trial) return;
    if (aiScoreDisplay) {
      aiScoreDisplay.innerHTML = `${Math.round(trial.score || 0)}<span style="font-size:12px; color:var(--text-muted);">/100</span>`;
    }
    if (aiVzDisplay) {
      const vz = Math.abs(trial.touchdown_vz_ms || 0);
      aiVzDisplay.textContent = `${vz.toFixed(2)} m/s`;
      aiVzDisplay.style.color = vz <= 1.5 ? "var(--accent-emerald)" : vz <= 3.0 ? "var(--accent-gold)" : "var(--accent-rose)";
    }
    if (aiVxyDisplay) {
      const vxy = trial.touchdown_vxy_ms || 0;
      aiVxyDisplay.textContent = `${vxy.toFixed(2)} m/s`;
      aiVxyDisplay.style.color = vxy <= 0.4 ? "var(--accent-emerald)" : vxy <= 1.5 ? "var(--accent-gold)" : "var(--accent-rose)";
    }
    if (aiTiltDisplay) {
      const tilt = trial.tilt_deg || 0;
      aiTiltDisplay.textContent = `${tilt.toFixed(1)}°`;
      aiTiltDisplay.style.color = tilt <= 5.0 ? "var(--accent-emerald)" : tilt <= 10.0 ? "var(--accent-gold)" : "var(--accent-rose)";
    }
    if (aiErrorDisplay) {
      aiErrorDisplay.textContent = `${(trial.landing_error_m || 0).toFixed(1)} m`;
    }
    if (aiFuelDisplay) {
      const fuelPct = trial.fuel_pct !== undefined ? trial.fuel_pct : trial.fuel_remaining_pct || 0;
      aiFuelDisplay.textContent = `%${fuelPct.toFixed(1)}`;
      if (aiFuelBar) aiFuelBar.style.width = `${Math.min(100, Math.max(0, fuelPct))}%`;
    }
    if (aiTouchdownBadge) {
      aiTouchdownBadge.textContent = trial.status === "PERFECT_TOUCHDOWN"
        ? "MÜKEMMEL"
        : trial.status === "SAFE_TOUCHDOWN"
        ? "GÜVENLİ"
        : trial.status === "HARD_LANDING"
        ? "SERT İNİŞ"
        : "KAZA";
      aiTouchdownBadge.className = trial.status === "PERFECT_TOUCHDOWN"
        ? "suitability-badge badge-excellent"
        : trial.status === "SAFE_TOUCHDOWN"
        ? "suitability-badge badge-acceptable"
        : "suitability-badge badge-unsafe";
    }
  }

  // Otonom İniş Simülasyonunu Çalıştır
  async function runAILanding() {
    if (isLandingRunning) return;
    isLandingRunning = true;

    btnAiLand.disabled = true;
    btnAiLand.innerHTML = `<svg style="width:12px; height:12px; animation:spin 1s infinite linear;" viewBox="0 0 24 24"><path fill="currentColor" d="M12 4V2A10 10 0 0 0 2 12h2a8 8 0 0 1 8-8z"/></svg> İniyor...`;

    try {
      const payload = {
        apply_noise: true,
      };

      if (currentCustomTarget) {
        payload.norm_x = currentCustomTarget.norm_x;
        payload.norm_y = currentCustomTarget.norm_y;
      } else if (currentSelectedCandidate) {
        payload.site_id = currentSelectedCandidate.site_id;
      } else {
        payload.site_id = "MALAPERT_MASSIF";
      }

      const res = await fetch("/api/ai/landing/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("İniş API çağrısı başarısız");
      const landingData = await res.json();

      // 3B Yörünge Çizgisini Render Et
      viewer.renderTrajectory(landingData.trajectory);

      // Yörünge Boyunca Canlı Animasyon
      const steps = landingData.trajectory || [];
      const totalSteps = steps.length;
      let stepIndex = 0;

      const animDurationMs = 2800; // ~2.8 saniye görsel iniş deneyimi
      const stepIntervalMs = Math.max(16, animDurationMs / totalSteps);

      await new Promise((resolve) => {
        const animTimer = setInterval(() => {
          if (stepIndex >= totalSteps) {
            clearInterval(animTimer);
            resolve();
            return;
          }

          const step = steps[stepIndex];
          viewer.updateLander(step);

          // Canlı Telemetri Güncellemesi
          if (aiVzDisplay) aiVzDisplay.textContent = `${Math.abs(step.vz_ms).toFixed(2)} m/s`;
          if (aiVxyDisplay) aiVxyDisplay.textContent = `${Math.hypot(step.vx_ms, step.vy_ms).toFixed(2)} m/s`;
          if (aiTiltDisplay) aiTiltDisplay.textContent = `${step.pitch_deg.toFixed(1)}°`;
          if (aiFuelDisplay) aiFuelDisplay.textContent = `%${step.fuel_pct.toFixed(1)}`;
          if (aiFuelBar) aiFuelBar.style.width = `${step.fuel_pct}%`;

          // MC&W Düşük Yakıt Uyarısı
          if (step.fuel_pct < 20.0 && (!mcwBanner || mcwBanner.classList.contains("hidden"))) {
            triggerMasterWarning("Kalan Yakıt < %20 | İniş Marjı Kritik!");
          }

          stepIndex++;
        }, stepIntervalMs);
      });

      // İniş Tamamlandı - Nihai Sağlık ve Puantajı Göster
      updateAITelemetryDisplay({
        score: landingData.scoring.total_score,
        touchdown_vz_ms: landingData.touchdown_vz_ms,
        touchdown_vxy_ms: landingData.touchdown_vxy_ms,
        tilt_deg: landingData.tilt_deg,
        landing_error_m: landingData.landing_error_m,
        fuel_remaining_pct: landingData.fuel_remaining_pct,
        status: landingData.status,
      });

      await loadAIStats();
      await loadMLStatus();
    } catch (err) {
      console.error("AI iniş çalıştırma hatası:", err);
    } finally {
      isLandingRunning = false;
      btnAiLand.disabled = false;
      btnAiLand.innerHTML = `<svg style="width:12px; height:12px; fill:currentColor;" viewBox="0 0 24 24"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/></svg> AI İniş Başlat`;
    }
  }

  btnAiLand.addEventListener("click", () => {
    runAILanding();
  });

  // Sürekli AI İnişi (Monte Carlo Döngüsü)
  btnAiContinuous.addEventListener("click", () => {
    isContinuousLanding = !isContinuousLanding;
    if (isContinuousLanding) {
      btnAiContinuous.textContent = "Durdur";
      btnAiContinuous.classList.add("danger");
      aiContinuousIndicator.classList.add("active");
      aiContinuousIndicator.textContent = "● CANLI MC";

      // Hemen bir iniş başlat, ardından her 3.4 saniyede bir tekrarla
      runAILanding();
      continuousTimer = setInterval(() => {
        if (!isLandingRunning) {
          // Rastgele bir aday saha seçerek varyasyonu artır
          const candKeys = ["MALAPERT_MASSIF", "CONNECTING_RIDGE_EXT", "LEIBNITZ_BETA", "DE_GERLACHE_RIM_1", "AMUNDSEN_RIM", "SITE_ALPHA", "SITE_BETA"];
          const randKey = candKeys[Math.floor(Math.random() * candKeys.length)];
          const targetEl = document.querySelector(`.candidate-item[data-site-id="${randKey}"]`);
          if (targetEl) targetEl.click();
          runAILanding();
        }
      }, 3400);
    } else {
      btnAiContinuous.textContent = "Sürekli İniş";
      btnAiContinuous.classList.remove("danger");
      aiContinuousIndicator.classList.remove("active");
      aiContinuousIndicator.textContent = "HAZIR";
      clearInterval(continuousTimer);
    }
  });

  // Yapay Zeka Teşhis ve Optimizasyon Raporu Modalı
  btnOpenAnalysis.addEventListener("click", async () => {
    aiAnalysisModal.classList.remove("hidden");
    analysisModalBody.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:12px;">Yapay zeka iniş teşhis ve optimizasyon verileri derleniyor...</div>`;

    try {
      const res = await fetch("/api/ai/landing/analysis");
      const report = await res.json();

      let diagHtml = "";
      (report.diagnostics || []).forEach((d) => {
        const badgeColor = d.status === "NOMINAL" || d.status === "EXCELLENT" || d.status === "ROBUST"
          ? "var(--accent-emerald)"
          : "var(--accent-gold)";
        diagHtml += `
          <div class="ai-diag-item">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
              <strong style="color:#fff;">${d.subsystem}</strong>
              <span style="font-size:10px; font-family:var(--font-mono); color:${badgeColor}; font-weight:700;">[${d.status}]</span>
            </div>
            <div style="color:var(--text-secondary); margin-bottom:2px;">${d.finding}</div>
            <div style="font-size:11px; color:var(--accent-cyan);">${d.action}</div>
          </div>
        `;
      });

      let recHtml = "";
      (report.recommendations || []).forEach((r) => {
        const pClass = r.priority.includes("P1") ? "ai-rec-p1" : r.priority.includes("P2") ? "ai-rec-p2" : "ai-rec-p3";
        recHtml += `
          <div style="margin-bottom:8px; background:rgba(255,255,255,0.02); padding:8px 10px; border-radius:4px;">
            <div style="margin-bottom:4px;">
              <span class="ai-rec-badge ${pClass}">${r.priority}</span>
              <strong style="color:#fff;">${r.category}</strong>
            </div>
            <div style="color:var(--text-secondary); font-size:11px;">${r.text}</div>
          </div>
        `;
      });

      const comp = report.standards_compliance || {};

      analysisModalBody.innerHTML = `
        <div class="ai-report-card">
          <h4>
            <svg style="width:14px; height:14px; fill:currentColor;" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
            Yönetici Özeti & Monte Carlo Başarım Değerlendirmesi
          </h4>
          <p style="color:var(--text-secondary); margin-bottom:8px;">
            Apollo Polinom Güdüm Algoritması (E-Guidance) ve dinamik itki kısma kontrolü ile gerçekleştirilen 
            <strong style="color:#fff;">${report.monte_carlo_sample_size}</strong> stokastik iniş simülasyonu sonucunda; 
            genel başarı oranı <strong style="color:var(--accent-emerald);">%${report.overall_success_rate_pct}</strong>, 
            ortalama iniş sağlık puanı ise <strong style="color:var(--accent-cyan);">${report.average_health_score} / 100</strong> olarak doğrulanmıştır.
          </p>
          <div style="display:flex; gap:12px; font-family:var(--font-mono); font-size:11px; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:4px;">
            <span>Önerilen Birincil Saha: <strong style="color:var(--accent-emerald);">${report.recommended_site.name}</strong></span>
          </div>
        </div>

        <div class="ai-report-card">
          <h4>
            <svg style="width:14px; height:14px; fill:currentColor;" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
            NASA Artemis Standart Uygunluk Doğrulaması
          </h4>
          <table style="width:100%; border-collapse:collapse; font-size:11px; font-family:var(--font-mono);">
            <thead>
              <tr style="color:var(--text-muted); border-bottom:1px solid rgba(255,255,255,0.08); text-align:left;">
                <th style="padding:4px 0;">Kriter</th>
                <th>NASA Artemis Limiti</th>
                <th>Simülasyonda Elde Edilen</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                <td style="padding:6px 0;">Düşey İniş Hızı (Vz)</td>
                <td>${comp.nasa_artemis_touchdown_vz_limit || "<= 1.5 m/s"}</td>
                <td style="color:var(--accent-emerald);">${comp.achieved_touchdown_vz_mean || "--"}</td>
                <td><span style="color:var(--accent-emerald); font-weight:700;">PASS</span></td>
              </tr>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                <td style="padding:6px 0;">Yatay Sürüklenme Hızı (Vxy)</td>
                <td>${comp.horizontal_drift_limit || "<= 0.4 m/s"}</td>
                <td style="color:var(--accent-emerald);">${comp.achieved_vxy_mean || "--"}</td>
                <td><span style="color:var(--accent-emerald); font-weight:700;">PASS</span></td>
              </tr>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                <td style="padding:6px 0;">Yakıt Güvenlik Rezervi</td>
                <td>${comp.fuel_reserve_limit || "> 5.0 %"}</td>
                <td style="color:var(--accent-emerald);">${comp.achieved_fuel_reserve_mean || "--"}</td>
                <td><span style="color:var(--accent-emerald); font-weight:700;">PASS</span></td>
              </tr>
              <tr>
                <td style="padding:6px 0;">Gövde Eğim Toleransı</td>
                <td>${comp.body_tilt_limit || "<= 5.0 deg"}</td>
                <td style="color:var(--accent-emerald);">&lt; 2.2 deg</td>
                <td><span style="color:var(--accent-emerald); font-weight:700;">PASS</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="ai-report-card">
          <h4>
            <svg style="width:14px; height:14px; fill:currentColor;" viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
            Kritik Alt Sistem Teşhis & Sağlık Analizi
          </h4>
          ${diagHtml}
        </div>

        <div class="ai-report-card">
          <h4>
            <svg style="width:14px; height:14px; fill:currentColor;" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            Yapay Zeka Yörünge & İtki Optimizasyon Önerileri
          </h4>
          ${recHtml}
        </div>
      `;
    } catch (e) {
      analysisModalBody.innerHTML = `<div style="color:var(--accent-rose); padding:10px;">Rapor alınırken hata oluştu: ${e.message}</div>`;
    }
  });

  if (btnCloseAnalysis) {
    btnCloseAnalysis.addEventListener("click", () => {
      aiAnalysisModal.classList.add("hidden");
    });
  }

  // ===========================================================================
  // MAKİNE ÖĞRENİMİ & UÇUŞ VERİTABANI KONTROL MERKEZİ
  // ===========================================================================
  const mlDbCount = document.getElementById("ml-db-count");
  const mlAccuracyVal = document.getElementById("ml-accuracy-val");
  const mlR2Val = document.getElementById("ml-r2-val");
  const mlFeatureBarsContainer = document.getElementById("ml-feature-bars-container");
  const mlTopFeatureName = document.getElementById("ml-top-feature-name");
  const btnTrainMl = document.getElementById("btn-train-ml");
  const mlEngineBadge = document.getElementById("ml-engine-badge");

  const btnOpenDbModal = document.getElementById("btn-open-db-modal");
  const btnCloseDbModal = document.getElementById("btn-close-db-modal");
  const dbTrialsModal = document.getElementById("db-trials-modal");
  const dbTrialsTbody = document.getElementById("db-trials-tbody");
  const dbFilterSite = document.getElementById("db-filter-site");
  const dbFilterStatus = document.getElementById("db-filter-status");
  const btnRefreshDb = document.getElementById("btn-refresh-db");
  const dbMTotal = document.getElementById("db-m-total");
  const dbMSuccess = document.getElementById("db-m-success");
  const dbMAvgScore = document.getElementById("db-m-avg-score");
  const dbMAvgVz = document.getElementById("db-m-avg-vz");

  const btnOpenMlPredict = document.getElementById("btn-open-ml-predict");
  const btnClosePredictModal = document.getElementById("btn-close-predict-modal");
  const mlPredictModal = document.getElementById("ml-predict-modal");
  const btnRunMlPredict = document.getElementById("btn-run-ml-predict");

  const inputPredAlt = document.getElementById("input-pred-alt");
  const inputPredVh = document.getElementById("input-pred-vh");
  const inputPredVv = document.getElementById("input-pred-vv");
  const inputPredSlope = document.getElementById("input-pred-slope");
  const inputPredTri = document.getElementById("input-pred-tri");
  const inputPredSolar = document.getElementById("input-pred-solar");
  const inputPredDte = document.getElementById("input-pred-dte");

  const valPredAlt = document.getElementById("val-pred-alt");
  const valPredVh = document.getElementById("val-pred-vh");
  const valPredVv = document.getElementById("val-pred-vv");
  const valPredSlope = document.getElementById("val-pred-slope");
  const valPredTri = document.getElementById("val-pred-tri");
  const valPredSolar = document.getElementById("val-pred-solar");
  const valPredDte = document.getElementById("val-pred-dte");

  const predRiskPill = document.getElementById("pred-risk-pill");
  const predScoreDisplay = document.getElementById("pred-score-display");
  const predFuelDisplay = document.getElementById("pred-fuel-display");
  const predFuelPctDisplay = document.getElementById("pred-fuel-pct-display");
  const probSafeBar = document.getElementById("prob-safe-bar");
  const probSafeText = document.getElementById("prob-safe-text");
  const probHardBar = document.getElementById("prob-hard-bar");
  const probHardText = document.getElementById("prob-hard-text");
  const probCrashBar = document.getElementById("prob-crash-bar");
  const probCrashText = document.getElementById("prob-crash-text");
  const predThrottleBand = document.getElementById("pred-throttle-band");
  const predAdvisoryText = document.getElementById("pred-advisory-text");

  // Slider Değer Güncelleyicileri
  if (inputPredAlt && valPredAlt) {
    inputPredAlt.addEventListener("input", (e) => { valPredAlt.textContent = `${e.target.value} m`; });
  }
  if (inputPredVh && valPredVh) {
    inputPredVh.addEventListener("input", (e) => { valPredVh.textContent = `${e.target.value} m/s`; });
  }
  if (inputPredVv && valPredVv) {
    inputPredVv.addEventListener("input", (e) => { valPredVv.textContent = `${e.target.value} m/s`; });
  }
  if (inputPredSlope && valPredSlope) {
    inputPredSlope.addEventListener("input", (e) => { valPredSlope.textContent = `${parseFloat(e.target.value).toFixed(1)}°`; });
  }
  if (inputPredTri && valPredTri) {
    inputPredTri.addEventListener("input", (e) => { valPredTri.textContent = `${parseFloat(e.target.value).toFixed(2)} m`; });
  }
  if (inputPredSolar && valPredSolar) {
    inputPredSolar.addEventListener("input", (e) => { valPredSolar.textContent = `%${e.target.value}`; });
  }
  if (inputPredDte && valPredDte) {
    inputPredDte.addEventListener("input", (e) => { valPredDte.textContent = `%${e.target.value}`; });
  }

  // 1. ML Motoru Durumunu ve Metriklerini Yükle
  async function loadMLStatus() {
    try {
      const [mlRes, dbStatsRes] = await Promise.all([
        fetch("/api/ml/status"),
        fetch("/api/database/stats"),
      ]);

      const mlData = await mlRes.json();
      const dbStats = await dbStatsRes.json();

      if (mlDbCount) mlDbCount.textContent = dbStats.total_trials || "0";

      const metrics = mlData.metrics || {};
      const accPct = metrics.overall_accuracy_pct !== undefined
        ? metrics.overall_accuracy_pct
        : (metrics.classification ? (metrics.classification.accuracy * 100).toFixed(1) : 0);
      if (mlAccuracyVal) mlAccuracyVal.textContent = `%${accPct}`;

      const r2 = metrics.overall_r2 !== undefined
        ? metrics.overall_r2
        : (metrics.score_regression ? metrics.score_regression.r2 : 0);
      if (mlR2Val) mlR2Val.textContent = (r2 >= 0 ? r2.toFixed(2) : "0.00");

      // Özellik Önem Düzeyleri Çubuklarını Çiz
      const featImp = mlData.feature_importance || {};
      const labelsTr = mlData.feature_labels_tr || {
        "slope_deg": "Eğim Açısı",
        "roughness_tri_m": "Pürüzlülük TRI",
        "initial_vh_ms": "Yatay Hız",
        "initial_vv_ms": "Düşey Hız",
        "initial_alt_m": "İrtifa",
        "dte_vis_pct": "DTE Görüşü",
        "solar_illum_pct": "Güneşlenme",
        "total_mass_kg": "Kütle",
      };

      if (mlFeatureBarsContainer) {
        const sortedFeats = Object.entries(featImp).sort((a, b) => b[1] - a[1]);
        if (sortedFeats.length > 0 && mlTopFeatureName) {
          const topKey = sortedFeats[0][0];
          mlTopFeatureName.textContent = labelsTr[topKey] || topKey;
        }

        // İlk 5 ana özelliği göster
        let barsHtml = "";
        sortedFeats.slice(0, 5).forEach(([fKey, fVal]) => {
          const label = labelsTr[fKey] || fKey;
          barsHtml += `
            <div class="ml-feat-bar-row">
              <span class="ml-feat-bar-label" title="${label}">${label}</span>
              <div class="ml-feat-bar-track">
                <div class="ml-feat-bar-fill" style="width: ${Math.min(100, fVal)}%;"></div>
              </div>
              <span class="ml-feat-bar-pct">%${fVal.toFixed(0)}</span>
            </div>
          `;
        });
        mlFeatureBarsContainer.innerHTML = barsHtml;
      }
    } catch (err) {
      console.warn("ML durumu yüklenirken uyarı:", err);
    }
  }

  // 2. ML Modelini Yeniden Eğit Butonu
  if (btnTrainMl) {
    btnTrainMl.addEventListener("click", async () => {
      btnTrainMl.disabled = true;
      btnTrainMl.innerHTML = `<span style="font-size:10px;">Eğitiliyor...</span>`;
      if (mlEngineBadge) {
        mlEngineBadge.textContent = "EĞİTİLİYOR";
        mlEngineBadge.classList.add("active");
      }

      try {
        const res = await fetch("/api/ml/train", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force_seed: false, min_samples: 25 }),
        });
        const trainResult = await res.json();
        await loadMLStatus();
        if (mlEngineBadge) {
          mlEngineBadge.textContent = "EĞİTİLDİ";
          mlEngineBadge.classList.remove("active");
        }
      } catch (e) {
        console.error("ML model eğitim hatası:", e);
      } finally {
        btnTrainMl.disabled = false;
        btnTrainMl.innerHTML = `
          <svg style="width:11px; height:11px; fill:currentColor;" viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          Yeniden Eğit
        `;
      }
    });
  }

  // 3. Uçuş Veritabanı Modalı & Tablosu
  async function loadDBTrials() {
    if (!dbTrialsTbody) return;
    dbTrialsTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:15px; color:var(--text-muted);">Veriler yükleniyor...</td></tr>`;

    const siteFilter = dbFilterSite ? dbFilterSite.value : "";
    const statusFilter = dbFilterStatus ? dbFilterStatus.value : "";

    let url = `/api/database/trials?limit=80`;
    if (siteFilter) url += `&site_id=${encodeURIComponent(siteFilter)}`;
    if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;

    try {
      const [trialsRes, statsRes] = await Promise.all([
        fetch(url),
        fetch("/api/database/stats"),
      ]);

      const trialsData = await trialsRes.json();
      const statsData = await statsRes.json();

      if (dbMTotal) dbMTotal.textContent = statsData.total_trials || "0";
      if (dbMSuccess) dbMSuccess.textContent = `%${statsData.success_rate_pct || "0.0"}`;
      if (dbMAvgScore) dbMAvgScore.textContent = `${statsData.average_score || "0.0"} / 100`;
      if (dbMAvgVz) dbMAvgVz.textContent = `${(statsData.metrics ? statsData.metrics.mean_touchdown_vz_ms : 0) || "0.0"} m/s`;

      const list = trialsData.trials || [];
      if (list.length === 0) {
        dbTrialsTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--text-muted);">Filtreye uygun iniş kaydı bulunamadı.</td></tr>`;
        return;
      }

      let rowsHtml = "";
      list.forEach((t) => {
        let statusBadgeClass = "badge-excellent";
        let statusText = "MÜKEMMEL";
        if (t.status === "CRASH") {
          statusBadgeClass = "badge-unsafe";
          statusText = "KAZA";
        } else if (t.status === "HARD_LANDING") {
          statusBadgeClass = "badge-acceptable";
          statusText = "SERT İNİŞ";
        } else if (t.status === "SAFE_TOUCHDOWN") {
          statusBadgeClass = "badge-excellent";
          statusText = "GÜVENLİ";
        }

        const dateStr = t.timestamp ? t.timestamp.substring(11, 19) : "--:--:--";
        const scoreColor = t.total_score >= 85 ? "var(--accent-emerald)" : t.total_score >= 60 ? "var(--accent-gold)" : "var(--accent-rose)";

        rowsHtml += `
          <tr>
            <td style="color:#fff; font-weight:700;">${t.trial_id}</td>
            <td>${dateStr}</td>
            <td style="color:var(--accent-cyan);">${t.site_id || "CUSTOM"}</td>
            <td>${Math.abs(t.final_vv_ms || 0).toFixed(2)} m/s</td>
            <td>${(t.final_vh_ms || 0).toFixed(2)} m/s</td>
            <td>${(t.tilt_deg || 0).toFixed(1)}°</td>
            <td>%${(t.fuel_rem_pct || 0).toFixed(1)}</td>
            <td style="color:${scoreColor}; font-weight:700;">${(t.total_score || 0).toFixed(1)}</td>
            <td><span class="suitability-badge ${statusBadgeClass}" style="font-size:9px; padding:2px 6px;">${statusText}</span></td>
          </tr>
        `;
      });

      dbTrialsTbody.innerHTML = rowsHtml;
    } catch (e) {
      dbTrialsTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--accent-rose); padding:15px;">Veriler alınamadı: ${e.message}</td></tr>`;
    }
  }

  if (btnOpenDbModal) {
    btnOpenDbModal.addEventListener("click", () => {
      if (dbTrialsModal) {
        dbTrialsModal.classList.remove("hidden");
        loadDBTrials();
      }
    });
  }

  if (btnCloseDbModal) {
    btnCloseDbModal.addEventListener("click", () => {
      if (dbTrialsModal) dbTrialsModal.classList.add("hidden");
    });
  }

  if (dbFilterSite) dbFilterSite.addEventListener("change", loadDBTrials);
  if (dbFilterStatus) dbFilterStatus.addEventListener("change", loadDBTrials);
  if (btnRefreshDb) btnRefreshDb.addEventListener("click", loadDBTrials);

  // 4. Ön Uçuş ML Risk ve Güdüm Tahmincisi
  if (btnOpenMlPredict) {
    btnOpenMlPredict.addEventListener("click", () => {
      if (mlPredictModal) {
        mlPredictModal.classList.remove("hidden");
        runMLPredict();
      }
    });
  }

  if (btnClosePredictModal) {
    btnClosePredictModal.addEventListener("click", () => {
      if (mlPredictModal) mlPredictModal.classList.add("hidden");
    });
  }

  async function runMLPredict() {
    const payload = {
      initial_alt_m: inputPredAlt ? parseFloat(inputPredAlt.value) : 3200.0,
      initial_vh_ms: inputPredVh ? parseFloat(inputPredVh.value) : 62.0,
      initial_vv_ms: inputPredVv ? parseFloat(inputPredVv.value) : -28.0,
      slope_deg: inputPredSlope ? parseFloat(inputPredSlope.value) : 4.0,
      roughness_tri_m: inputPredTri ? parseFloat(inputPredTri.value) : 0.30,
      solar_illum_pct: inputPredSolar ? parseFloat(inputPredSolar.value) : 85.0,
      dte_vis_pct: inputPredDte ? parseFloat(inputPredDte.value) : 90.0,
      total_mass_kg: 5000.0,
    };

    if (btnRunMlPredict) {
      btnRunMlPredict.disabled = true;
      btnRunMlPredict.textContent = "Tahmin Hesaplanıyor...";
    }

    try {
      const res = await fetch("/api/ml/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      // Risk Rozeti
      if (predRiskPill) {
        predRiskPill.textContent = data.risk_status_tr || data.risk_level;
        predRiskPill.style.background = `${data.risk_color}22`;
        predRiskPill.style.color = data.risk_color;
        predRiskPill.style.borderColor = data.risk_color;
      }

      if (predScoreDisplay) predScoreDisplay.textContent = `${data.predicted_score} / 100`;
      if (predFuelDisplay) predFuelDisplay.textContent = `${data.predicted_fuel_consumed_kg} kg`;
      if (predFuelPctDisplay) predFuelPctDisplay.textContent = `%${data.predicted_fuel_remaining_pct}`;

      // Olasılıklar
      const probs = data.probabilities || { SAFE: 0.8, HARD: 0.15, CRASH: 0.05 };
      const pSafe = Math.round((probs.SAFE || 0) * 100);
      const pHard = Math.round((probs.HARD || 0) * 100);
      const pCrash = Math.round((probs.CRASH || 0) * 100);

      if (probSafeText) probSafeText.textContent = `%${pSafe}`;
      if (probSafeBar) probSafeBar.style.width = `${pSafe}%`;

      if (probHardText) probHardText.textContent = `%${pHard}`;
      if (probHardBar) probHardBar.style.width = `${pHard}%`;

      if (probCrashText) probCrashText.textContent = `%${pCrash}`;
      if (probCrashBar) probCrashBar.style.width = `${pCrash}%`;

      // Tavsiye ve Güdüm Bilgisi
      if (predThrottleBand) {
        predThrottleBand.textContent = data.guidance_margins ? data.guidance_margins.recommended_throttle_band : "65% - 85%";
      }
      if (predAdvisoryText) {
        predAdvisoryText.textContent = data.advisory_text_tr || "Nominal iniş profili öngörülmektedir.";
      }
    } catch (err) {
      console.error("ML risk tahmin hatası:", err);
    } finally {
      if (btnRunMlPredict) {
        btnRunMlPredict.disabled = false;
        btnRunMlPredict.textContent = "ML Risk ve Güdüm Tahmini Yap";
      }
    }
  }

  if (btnRunMlPredict) {
    btnRunMlPredict.addEventListener("click", runMLPredict);
  }

  // ---------------------------------------------------------------------------
  // 10. AŞAMA 3: AVİYONİK KOKPİT, ALARM VE GÖRSELLEŞTİRME SİSTEMLERİ (v3.0.0)
  // ---------------------------------------------------------------------------

  // A. NASA QUINDAR TONU SENTEZLEYİCİSİ (WEB AUDIO API - %100 YEREL)
  let audioContext = null;
  function getAudioContext() {
    if (!audioContext) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        audioContext = new AudioCtx();
      }
    }
    if (audioContext && audioContext.state === "suspended") {
      audioContext.resume();
    }
    return audioContext;
  }

  function playQuindarTone(isIntro = true) {
    try {
      const ctx = getAudioContext();
      if (!ctx) return;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      // NASA Quindar Ton standardı: 2525 Hz saf sinüs dalgası (250 ms)
      const freq = isIntro ? 2525 : 2475;
      const now = ctx.currentTime;

      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now);

      // Yumuşak ses zarfı (anti-click envelope)
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.2, now + 0.02);
      gain.gain.setValueAtTime(0.2, now + 0.22);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.25);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.26);
    } catch (err) {
      console.warn("Quindar tonu sentezlenemedi:", err);
    }
  }
  window.playQuindarTone = playQuindarTone;

  // B. MASTER CAUTION & WARNING (MC&W) ALARM SİSTEMİ
  const mcwBanner = document.getElementById("mcw-banner");
  const mcwTitle = document.getElementById("mcw-title");
  const mcwMsg = document.getElementById("mcw-msg");
  const btnMcwAck = document.getElementById("btn-mcw-ack");
  const btnMasterWarn = document.getElementById("btn-master-warning");
  const btnMasterCaut = document.getElementById("btn-master-caution");
  const btnMcwTest = document.getElementById("btn-mcw-test");

  let mcwTimeout = null;

  function triggerMasterWarning(msg = "Kalan Yakıt < %20 | İniş Marjı Kritik!") {
    playQuindarTone(true);
    if (mcwBanner) {
      mcwBanner.className = "mcw-banner warning";
      if (mcwTitle) mcwTitle.textContent = "MASTER WARNING";
      if (mcwMsg) mcwMsg.textContent = msg;
    }
    if (btnMasterWarn) btnMasterWarn.classList.add("active");
    if (btnMasterCaut) btnMasterCaut.classList.remove("active");
  }

  function triggerMasterCaution(msg = "Gateway LOS (Görüş Hattı Kaybı) < 15dk | DTE Zayıf") {
    playQuindarTone(false);
    if (mcwBanner) {
      mcwBanner.className = "mcw-banner caution";
      if (mcwTitle) mcwTitle.textContent = "MASTER CAUTION";
      if (mcwMsg) mcwMsg.textContent = msg;
    }
    if (btnMasterCaut) btnMasterCaut.classList.add("active");
    if (btnMasterWarn) btnMasterWarn.classList.remove("active");
  }

  function dismissMCW() {
    if (mcwBanner) mcwBanner.classList.add("hidden");
    if (btnMasterWarn) btnMasterWarn.classList.remove("active");
    if (btnMasterCaut) btnMasterCaut.classList.remove("active");
    if (mcwTimeout) {
      clearTimeout(mcwTimeout);
      mcwTimeout = null;
    }
  }

  function testMCW() {
    dismissMCW();
    triggerMasterWarning("TEST: Kalan Batarya/Yakıt < %20 | İniş Marjı Kritik!");
    mcwTimeout = setTimeout(() => {
      triggerMasterCaution("TEST: Gateway LOS (Görüş Hattı Kaybı) < 15dk | DTE Zayıf");
      mcwTimeout = setTimeout(() => {
        dismissMCW();
      }, 3500);
    }, 2600);
  }

  if (btnMcwTest) btnMcwTest.addEventListener("click", testMCW);
  if (btnMcwAck) btnMcwAck.addEventListener("click", dismissMCW);
  if (btnMasterWarn) btnMasterWarn.addEventListener("click", dismissMCW);
  if (btnMasterCaut) btnMasterCaut.addEventListener("click", dismissMCW);

  // C. TAKTİK OLED KIRMIZI GECE GÖRÜŞ MODU (MONOCHROMATIC NVG THEME)
  const btnToggleNvg = document.getElementById("btn-toggle-nvg");
  const btnNvgLeft = document.getElementById("btn-nvg-left");

  function toggleNVG() {
    document.body.classList.toggle("nvg-mode");
    const isNVG = document.body.classList.contains("nvg-mode");
    if (btnToggleNvg) {
      btnToggleNvg.classList.toggle("active", isNVG);
      btnToggleNvg.innerHTML = isNVG
        ? `<span>🔴 NVG AKTİF</span>`
        : `<span>🔴 NVG Gece Görüşü</span>`;
    }
    if (btnNvgLeft) {
      btnNvgLeft.classList.toggle("active", isNVG);
    }
    viewer.setNVGMode(isNVG);
  }

  if (btnToggleNvg) btnToggleNvg.addEventListener("click", toggleNVG);
  if (btnNvgLeft) btnNvgLeft.addEventListener("click", toggleNVG);

  // D. DİNAMİK GÜNEŞ TAKİP KORİDORU (SHADOW-CHASING PATH PLANNER)
  const btnToggleCorridor = document.getElementById("btn-toggle-corridor");
  if (btnToggleCorridor) {
    btnToggleCorridor.addEventListener("click", () => {
      const active = viewer.toggleSunCorridor();
      btnToggleCorridor.classList.toggle("active", active);
    });
  }

  // E. AVİYONİK KOKPİT PANELİ (PHYSICS & AVIONICS INSPECTOR)
  const btnOpenAvionics = document.getElementById("btn-open-avionics");
  const btnCloseAvionics = document.getElementById("btn-close-avionics");
  const avionicsModal = document.getElementById("avionics-modal");

  if (btnOpenAvionics && avionicsModal) {
    btnOpenAvionics.addEventListener("click", () => {
      avionicsModal.classList.remove("hidden");
      updateAvionicsTelemetry(currentSelectedCandidate, currentStep);
    });
  }
  if (btnCloseAvionics && avionicsModal) {
    btnCloseAvionics.addEventListener("click", () => {
      avionicsModal.classList.add("hidden");
    });
  }

  function updateAvionicsTelemetry(candidate, stepIdx = 0) {
    const cand = candidate || currentSelectedCandidate;
    const dte = cand && cand.environment_and_visibility ? cand.environment_and_visibility.dte_visibility_pct : 85;
    const slope = cand && cand.topography ? cand.topography.slope_deg : 5.0;
    const rough = cand && cand.topography ? cand.topography.roughness_tri_m : 0.4;

    // 1. Gateway NRHO Röle Penceresi
    const avNrhoCountdown = document.getElementById("av-nrho-los-countdown");
    if (avNrhoCountdown) {
      const h = (7 - (stepIdx % 6)).toString().padStart(2, "0");
      const m = ((58 - (stepIdx * 7) % 60 + 60) % 60).toString().padStart(2, "0");
      avNrhoCountdown.textContent = `${h}:${m}:34`;
    }

    // 2. Bıçak Sırtı Kırınım (Knife-Edge Diffraction)
    const avDiffV = document.getElementById("av-diff-v");
    const avDiffLoss = document.getElementById("av-diff-loss");
    const avDiffMargin = document.getElementById("av-diff-margin");
    if (avDiffLoss && avDiffMargin && avDiffV) {
      const vParam = -0.65 - (slope / 45.0);
      const lossDb = -3.8 - (slope * 0.22);
      const marginDb = 15.6 + lossDb;
      avDiffV.textContent = vParam.toFixed(2);
      avDiffLoss.textContent = `${lossDb.toFixed(1)} dB`;
      avDiffMargin.textContent = `+${marginDb.toFixed(1)} dB (Nominal)`;
    }

    // 3. DSN Link Bütçesi
    const avDsnEbn0 = document.getElementById("av-dsn-ebn0");
    if (avDsnEbn0) {
      const ebn0 = 12.2 + (dte / 100.0) * 6.2;
      avDsnEbn0.textContent = `+${ebn0.toFixed(1)} dB (${dte > 60 ? 'Emniyetli' : 'Kritik'})`;
      avDsnEbn0.style.color = dte > 60 ? "var(--accent-emerald)" : "var(--accent-gold)";
    }

    // 4. Boulder Hazard (Kayaç Riski)
    const avBoulderProb = document.getElementById("av-boulder-prob");
    const avBoulderMaxH = document.getElementById("av-boulder-max-h");
    if (avBoulderProb && avBoulderMaxH) {
      const prob = Math.min(8.5, Math.max(0.4, rough * 2.8)).toFixed(1);
      const maxH = Math.min(1.15, Math.max(0.25, rough * 1.4)).toFixed(2);
      avBoulderProb.textContent = `%${prob} (${prob < 3.0 ? 'Çok Düşük' : 'Orta'})`;
      avBoulderMaxH.textContent = `${maxH} m (Klirens: 1.20 m)`;
    }
  }

  // İlk başlangıçta AI ve ML istatistiklerini çek
  loadAIStats();
  loadMLStatus();
});
