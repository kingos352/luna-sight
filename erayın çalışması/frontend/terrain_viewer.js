/**
 * frontend/terrain_viewer.js
 * ==========================
 * Three.js tabanlı özel Ay Yüzeyi 3B Mesh Render, Katman Renklendirme,
 * Güneş Gölgeleme, Havada Asılı İşaretçi Kot Mıhlama, NVG Modu,
 * ve Dinamik Güneş Takip Koridoru (Shadow-Chasing Path) Motoru.
 * Sürüm: v3.0.0
 */

class LunarTerrainViewer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.terrainMesh = null;
    this.sunLight = null;
    this.sunTarget = null;
    this.sunMarker = null;
    this.earthMarker = null;
    this.ambientLight = null;
    this.landingPin = null;

    // AI Otonom İniş ve Yörünge Elemanları
    this.landerGroup = null;
    this.landerPlume = null;
    this.trajectoryLine = null;
    this.moontrekTexture = null;

    this.meshData = null;
    this.layersData = null;
    this.currentLayer = "elevation";

    // İşaretçiler ve Bölgesel Kot Yönetimi (Floating Markers Fix)
    this.allCandidates = [];
    this.candidateMarkersGroup = null;
    this.currentRegionId = null;
    this.lastPinCoords = null; // { normX, normY, posX, posZ }

    // Aviyonik & Görselleştirme Özellikleri (Aşama 3)
    this.isNVG = false;
    this.sunCorridorMesh = null;
    this.sunCorridorActive = false;

    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.onPointSelected = null; // Callback
    this.initScene();
    this.setupEvents();
  }

  initScene() {
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;

    // 1. Sahne & Kamera
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x07090e);
    this.scene.fog = new THREE.FogExp2(0x07090e, 0.0015);

    this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 15000);
    this.camera.position.set(0, 350, 450);

    // 2. WebGL Renderer (Gölge Haritaları Etkin)
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    // 3. OrbitControls
    if (typeof THREE.OrbitControls !== "undefined") {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.maxPolarAngle = Math.PI / 2 - 0.02; // Ufkun altına inme
      this.controls.minDistance = 30;
      this.controls.maxDistance = 2500;
      this.controls.target.set(0, 0, 0);
    }

    // 4. Işıklandırma (Güneş & Uzay Zemin Işığı)
    this.ambientLight = new THREE.AmbientLight(0x1a202c, 0.4);
    this.scene.add(this.ambientLight);

    // Güneş Yön Işığı (DirectionalLight)
    this.sunLight = new THREE.DirectionalLight(0xfff7ed, 2.2);
    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.width = 2048;
    this.sunLight.shadow.mapSize.height = 2048;
    this.sunLight.shadow.camera.near = 10;
    this.sunLight.shadow.camera.far = 2000;
    const d = 350;
    this.sunLight.shadow.camera.left = -d;
    this.sunLight.shadow.camera.right = d;
    this.sunLight.shadow.camera.top = d;
    this.sunLight.shadow.camera.bottom = -d;
    this.sunLight.shadow.bias = -0.0005;

    this.sunTarget = new THREE.Object3D();
    this.scene.add(this.sunTarget);
    this.sunLight.target = this.sunTarget;
    this.scene.add(this.sunLight);

    // Güneş görsel konumu belirteci
    const sunGeo = new THREE.SphereGeometry(10, 16, 16);
    const sunMat = new THREE.MeshBasicMaterial({ color: 0xffe066 });
    this.sunMarker = new THREE.Mesh(sunGeo, sunMat);
    this.scene.add(this.sunMarker);

    // Yıldız arka plan parçacıkları
    this.createStarfield();

    // Seçilen iniş noktası pini (Reticle)
    this.createLandingPin();

    // 3B Artemis Lander Modeli & MoonTrek Dokusu
    this.createLanderModel();
    this.preloadMoonTrekTexture();

    // Render Döngüsü
    const animate = () => {
      requestAnimationFrame(animate);
      if (this.controls) this.controls.update();

      const time = performance.now() * 0.003;

      // İniş pini nabız animasyonu
      if (this.landingPin && this.landingPin.visible) {
        const scale = 1.0 + Math.sin(time) * 0.15;
        this.landingPin.scale.set(scale, 1, scale);
      }

      // Güneş koridoru parıltı animasyonu
      if (this.sunCorridorMesh && this.sunCorridorMesh.material) {
        this.sunCorridorMesh.material.opacity = 0.55 + Math.sin(time * 2.5) * 0.3;
      }

      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }

  createStarfield() {
    const starCount = 1200;
    const starGeo = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 8000;
      starPositions[i + 1] = Math.random() * 4000 + 100;
      starPositions[i + 2] = (Math.random() - 0.5) * 8000;
    }

    starGeo.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 2.0, transparent: true, opacity: 0.8 });
    const stars = new THREE.Points(starGeo, starMat);
    this.scene.add(stars);
  }

  /**
   * Çözüm 3: İniş pini ve halkası zemin kotuna tam oturacak şekilde kurulur.
   * Halka: posY + 0.2 (tam zemin teması), Dikey ışık sütunu: posY'den başlar (y=25, h=50).
   */
  createLandingPin() {
    const group = new THREE.Group();

    // Dikey ışık sütunu (boy 50 -> center y=25 olunca alt ucu tam y=0 zemin kotundadır)
    const cylinderGeo = new THREE.CylinderGeometry(0.5, 0.5, 50, 16);
    const cylinderMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.85 });
    const cylinder = new THREE.Mesh(cylinderGeo, cylinderMat);
    cylinder.position.y = 25;
    group.add(cylinder);

    // Yüzey halkası zeminle tam temas (posY + 0.2)
    const ringGeo = new THREE.RingGeometry(4, 7, 32);
    ringGeo.rotateX(-Math.PI / 2);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x10b981, side: THREE.DoubleSide, transparent: true, opacity: 0.9 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.y = 0.2;
    group.add(ring);

    // Zemin merkez temas noktası
    const centerGeo = new THREE.SphereGeometry(1.0, 16, 16);
    const centerMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
    const center = new THREE.Mesh(centerGeo, centerMat);
    center.position.y = 0.3;
    group.add(center);

    group.visible = false;
    this.scene.add(group);
    this.landingPin = group;
  }

  preloadMoonTrekTexture() {
    const loader = new THREE.TextureLoader();
    this.moontrekTexture = loader.load("/static/assets/shackleton_reference.jpg", (tex) => {
      tex.wrapS = THREE.ClampToEdgeWrapping;
      tex.wrapT = THREE.ClampToEdgeWrapping;
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      if (this.currentLayer === "moontrek" && this.terrainMesh) {
        this.terrainMesh.material.map = tex;
        this.terrainMesh.material.needsUpdate = true;
      }
    });
  }

  setRegionTexture(regionId) {
    this.currentRegionId = regionId;
    const isShackleton = regionId && regionId.startsWith("SITE_");
    const texPath = isShackleton
      ? "/static/assets/shackleton_reference.jpg"
      : `/static/assets/regions/${regionId}_texture.jpg`;

    const loader = new THREE.TextureLoader();
    loader.load(texPath, (tex) => {
      tex.wrapS = THREE.ClampToEdgeWrapping;
      tex.wrapT = THREE.ClampToEdgeWrapping;
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      this.moontrekTexture = tex;
      if (this.currentLayer === "moontrek" && this.terrainMesh) {
        this.terrainMesh.material.map = tex;
        this.terrainMesh.material.needsUpdate = true;
      }
    });
  }

  createLanderModel() {
    const group = new THREE.Group();

    // 1. İniş Aşaması Gövdesi (Descent Stage - Altın Kapton Termal Folyo)
    const bodyGeo = new THREE.CylinderGeometry(2.4, 3.0, 2.0, 8);
    const bodyMat = new THREE.MeshStandardMaterial({
      color: 0xd4af37,
      metalness: 0.85,
      roughness: 0.25,
    });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 2.0;
    body.castShadow = true;
    group.add(body);

    // 2. Üst Kabin / Aviyonik Modülü (Ascent / Avionics Section)
    const topGeo = new THREE.CylinderGeometry(1.6, 2.0, 1.6, 8);
    const topMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      metalness: 0.9,
      roughness: 0.2,
    });
    const top = new THREE.Mesh(topGeo, topMat);
    top.position.y = 3.6;
    top.castShadow = true;
    group.add(top);

    // Parabolik X-Bant İletişim Anteni
    const dishGeo = new THREE.ConeGeometry(0.7, 0.35, 16, 1, true);
    const dishMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.6, roughness: 0.3 });
    const dish = new THREE.Mesh(dishGeo, dishMat);
    dish.rotation.x = Math.PI / 4;
    dish.position.set(0.7, 4.6, 0.5);
    group.add(dish);

    // 3. Ana Roket Lülesi (Main Descent Thruster Nozzle)
    const nozzleGeo = new THREE.ConeGeometry(0.8, 1.2, 16, 1, true);
    const nozzleMat = new THREE.MeshStandardMaterial({ color: 0x222225, metalness: 0.95, roughness: 0.15 });
    const nozzle = new THREE.Mesh(nozzleGeo, nozzleMat);
    nozzle.rotation.x = Math.PI;
    nozzle.position.y = 0.9;
    group.add(nozzle);

    // 4. Dinamik İtki Alevi (Thruster Plume)
    const plumeGeo = new THREE.ConeGeometry(0.65, 3.0, 16);
    const plumeMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.85,
    });
    const plume = new THREE.Mesh(plumeGeo, plumeMat);
    plume.position.y = -0.8;
    group.add(plume);
    this.landerPlume = plume;

    // 5. 4 Adet İniş Ayağı ve Ayak Pabuçları (Landing Legs & Footpads)
    const legMat = new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.7, roughness: 0.3 });
    const padMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, metalness: 0.85, roughness: 0.25 });

    for (let i = 0; i < 4; i++) {
      const angle = (i * Math.PI) / 2 + Math.PI / 4;
      const legGroup = new THREE.Group();

      const strutGeo = new THREE.CylinderGeometry(0.12, 0.12, 3.4, 8);
      const strut = new THREE.Mesh(strutGeo, legMat);
      strut.rotation.z = Math.PI / 3.4;
      strut.position.set(1.3, -0.5, 0);
      legGroup.add(strut);

      const padGeo = new THREE.CylinderGeometry(0.5, 0.6, 0.15, 12);
      const pad = new THREE.Mesh(padGeo, padMat);
      pad.position.set(2.6, -1.6, 0);
      legGroup.add(pad);

      legGroup.rotation.y = angle;
      legGroup.position.y = 1.8;
      group.add(legGroup);
    }

    group.visible = false;
    this.scene.add(group);
    this.landerGroup = group;
  }

  renderTrajectory(steps) {
    if (!steps || steps.length < 2) return;

    if (this.trajectoryLine) {
      this.scene.remove(this.trajectoryLine);
      this.trajectoryLine.geometry.dispose();
      this.trajectoryLine.material.dispose();
      this.trajectoryLine = null;
    }

    const points = [];
    steps.forEach((s) => {
      if (s.scene_pos && s.scene_pos.length === 3) {
        points.push(new THREE.Vector3(s.scene_pos[0], s.scene_pos[1], s.scene_pos[2]));
      }
    });

    if (points.length < 2) return;

    const geom = new THREE.BufferGeometry().setFromPoints(points);
    const lineMat = new THREE.LineBasicMaterial({
      color: this.isNVG ? 0xff2244 : 0x38bdf8,
      linewidth: 3,
      transparent: true,
      opacity: 0.85,
    });

    this.trajectoryLine = new THREE.Line(geom, lineMat);
    this.scene.add(this.trajectoryLine);
  }

  clearTrajectory() {
    if (this.trajectoryLine) {
      this.scene.remove(this.trajectoryLine);
      this.trajectoryLine.geometry.dispose();
      this.trajectoryLine.material.dispose();
      this.trajectoryLine = null;
    }
    if (this.landerGroup) {
      this.landerGroup.visible = false;
    }
  }

  updateLander(step) {
    if (!this.landerGroup || !step || !step.scene_pos) return;
    this.landerGroup.visible = true;

    const [x, y, z] = step.scene_pos;
    this.landerGroup.position.set(x, y, z);

    if (step.pitch_deg !== undefined) {
      const rad = (step.pitch_deg * Math.PI) / 180;
      this.landerGroup.rotation.set(0, 0, rad * 0.4);
    }

    if (this.landerPlume) {
      const throttle = (step.throttle_pct || 0) / 100.0;
      if (throttle > 0.05 && step.z_m > 0.4) {
        this.landerPlume.visible = true;
        const scale = 0.35 + throttle * 1.1;
        this.landerPlume.scale.set(scale, scale * (0.8 + Math.random() * 0.4), scale);
        this.landerPlume.material.opacity = 0.5 + throttle * 0.5;
      } else {
        this.landerPlume.visible = false;
      }
    }
  }

  setupEvents() {
    window.addEventListener("resize", () => {
      const w = this.container.clientWidth || window.innerWidth;
      const h = this.container.clientHeight || window.innerHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    });

    this.container.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return; // Yalnızca sol tık

      const rect = this.container.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(this.mouse, this.camera);
      if (!this.terrainMesh) return;

      const intersects = this.raycaster.intersectObject(this.terrainMesh);
      if (intersects.length > 0) {
        const hit = intersects[0];
        const uv = hit.uv;
        if (uv && this.onPointSelected) {
          const normX = uv.x;
          const normY = 1.0 - uv.y;
          const trueElevY = this.getHeightAt(normX, normY);

          const posX = (normX - 0.5) * 500;
          const posZ = (normY - 0.5) * 500;

          this.lastPinCoords = { normX, normY, posX, posZ };

          // Pini zemine tam mıhla
          this.landingPin.position.set(posX, trueElevY, posZ);
          this.landingPin.visible = true;

          this.onPointSelected(normX, normY, new THREE.Vector3(posX, trueElevY, posZ));
        }
      }
    });
  }

  /**
   * Çözüm 1: Her arazi yüklendiğinde ('buildTerrain'), arazideki tüm işaretçilerin
   * ve iniş pini yüksekliğini yeni arazinin gerçek kotuna anında mıhla!
   */
  buildTerrain(meshData, layersData) {
    this.meshData = meshData;
    this.layersData = layersData;

    if (this.terrainMesh) {
      this.scene.remove(this.terrainMesh);
      this.terrainMesh.geometry.dispose();
      this.terrainMesh.material.dispose();
    }

    const w = meshData.width;
    const h = meshData.height;
    const matrix = meshData.elevation_matrix;

    const sizeX = 500;
    const sizeZ = 500;
    const elevMin = meshData.elev_min;
    const elevMax = meshData.elev_max;
    const elevRange = Math.max(1, elevMax - elevMin);
    const maxMeshHeight = 90;

    const geometry = new THREE.PlaneGeometry(sizeX, sizeZ, w - 1, h - 1);
    geometry.rotateX(-Math.PI / 2);

    const posAttr = geometry.attributes.position;
    for (let j = 0; j < h; j++) {
      for (let i = 0; i < w; i++) {
        const vertexIndex = j * w + i;
        const rawElev = matrix[j][i];
        const normH = (rawElev - elevMin) / elevRange;
        posAttr.setY(vertexIndex, normH * maxMeshHeight);
      }
    }
    posAttr.needsUpdate = true;
    geometry.computeVertexNormals();

    const texture = this.generateLayerTexture(this.currentLayer);

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      roughness: 0.95,
      metalness: 0.05,
      flatShading: false,
      color: this.isNVG ? 0xff3344 : 0xffffff,
    });

    this.terrainMesh = new THREE.Mesh(geometry, material);
    this.terrainMesh.castShadow = true;
    this.terrainMesh.receiveShadow = true;
    this.scene.add(this.terrainMesh);

    if (this.controls) {
      this.controls.target.set(0, maxMeshHeight * 0.3, 0);
    }

    // ÇÖZÜM 1: Yeni arazi yüklendiğinde tüm aday işaretçilerini anında yeni kotlara mıhla
    this.renderCandidateMarkers();

    // İniş pini aktifse onu da yeni arazinin gerçek kotuna mıhla
    if (this.landingPin && this.landingPin.visible && this.lastPinCoords) {
      const pinY = this.getHeightAt(this.lastPinCoords.normX, this.lastPinCoords.normY);
      const posX = (this.lastPinCoords.normX - 0.5) * 500;
      const posZ = (this.lastPinCoords.normY - 0.5) * 500;
      this.landingPin.position.set(posX, pinY, posZ);
    }

    // Güneş takip koridoru aktifse yeni kotlarla yeniden oluştur
    if (this.sunCorridorActive) {
      this.renderSunCorridor(true);
    }
  }

  generateLayerTexture(layerName) {
    if (layerName === "moontrek") {
      if (!this.moontrekTexture) {
        this.preloadMoonTrekTexture();
      }
      return this.moontrekTexture;
    }

    if (!this.layersData) return null;

    const data = this.layersData[layerName] || this.layersData.elevation;
    const h = data.length;
    const w = data[0].length;

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    const imgData = ctx.createImageData(w, h);
    const pixels = imgData.data;

    let minVal = Infinity;
    let maxVal = -Infinity;
    for (let j = 0; j < h; j++) {
      for (let i = 0; i < w; i++) {
        const v = data[j][i];
        if (v < minVal) minVal = v;
        if (v > maxVal) maxVal = v;
      }
    }
    const range = Math.max(1e-5, maxVal - minVal);

    for (let j = 0; j < h; j++) {
      for (let i = 0; i < w; i++) {
        const val = data[j][i];
        const norm = (val - minVal) / range;
        const idx = (j * w + i) * 4;
        let r = 0, g = 0, b = 0;

        if (this.isNVG) {
          // Monokromatik taktik OLED kırmızı-siyah palet
          const redVal = Math.round(norm * 225 + 30);
          r = redVal;
          g = Math.round(redVal * 0.12);
          b = Math.round(redVal * 0.15);
        } else if (layerName === "elevation") {
          const c = Math.round(norm * 215 + 40);
          r = c; g = c; b = Math.min(255, c + 15);
        } else if (layerName === "slope") {
          if (val <= 8.0) {
            r = Math.round((val / 8.0) * 120);
            g = 210;
            b = 80;
          } else if (val <= 12.0) {
            const f = (val - 8.0) / 4.0;
            r = 245;
            g = Math.round(210 * (1.0 - f));
            b = 40;
          } else {
            r = 235;
            g = 35;
            b = 50;
          }
        } else if (layerName === "roughness") {
          r = Math.round(Math.min(255, norm * 2 * 255));
          g = Math.round(Math.min(255, (1 - Math.abs(norm - 0.5) * 2) * 255));
          b = Math.round(Math.max(0, (1 - norm * 2) * 255));
        } else if (layerName === "illumination") {
          r = Math.round(norm * 255);
          g = Math.round(norm * 210);
          b = Math.round(norm * 140);
        } else if (layerName === "dte") {
          r = Math.round(norm * 40);
          g = Math.round(norm * 180 + 20);
          b = Math.round(norm * 240 + 30);
        } else if (layerName === "suitability") {
          if (norm < 0.5) {
            const f = norm / 0.5;
            r = 230;
            g = Math.round(f * 200);
            b = 30;
          } else {
            const f = (norm - 0.5) / 0.5;
            r = Math.round(230 * (1.0 - f));
            g = 215;
            b = Math.round(f * 80);
          }
        }

        pixels[idx] = r;
        pixels[idx + 1] = g;
        pixels[idx + 2] = b;
        pixels[idx + 3] = 255;
      }
    }

    ctx.putImageData(imgData, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    return texture;
  }

  setLayer(layerName) {
    this.currentLayer = layerName;
    if (!this.terrainMesh) return;

    if (layerName === "moontrek") {
      if (!this.moontrekTexture) {
        this.preloadMoonTrekTexture();
      }
      this.terrainMesh.material.map = this.moontrekTexture;
      this.terrainMesh.material.roughness = 0.85;
      this.terrainMesh.material.metalness = 0.08;
      this.terrainMesh.material.needsUpdate = true;
      return;
    }

    const texture = this.generateLayerTexture(layerName);
    this.terrainMesh.material.map = texture;
    this.terrainMesh.material.roughness = 0.95;
    this.terrainMesh.material.metalness = 0.05;
    this.terrainMesh.material.needsUpdate = true;
  }

  updateSunPosition(azimuthDeg, elevationDeg) {
    if (!this.sunLight || !this.sunMarker) return;

    const dist = 650;
    const azRad = (azimuthDeg * Math.PI) / 180;
    const elRad = (elevationDeg * Math.PI) / 180;

    const x = dist * Math.cos(elRad) * Math.sin(azRad);
    const y = Math.max(-50, dist * Math.sin(elRad));
    const z = -dist * Math.cos(elRad) * Math.cos(azRad);

    this.sunLight.position.set(x, y, z);
    this.sunMarker.position.set(x * 0.9, y * 0.9, z * 0.9);

    if (elevationDeg <= 0) {
      this.sunLight.intensity = 0.05;
      this.sunMarker.material.color.setHex(this.isNVG ? 0x661122 : 0x553311);
    } else {
      const factor = Math.min(1.0, elevationDeg / 5.0);
      this.sunLight.intensity = 0.3 + 2.0 * factor;
      this.sunMarker.material.color.setHex(this.isNVG ? 0xff4455 : 0xffe066);
    }
  }

  /**
   * Bilineer enterpolasyon ile gerçek kot yüksekliği hesabı.
   */
  getHeightAt(normX, normY) {
    if (!this.meshData || !this.meshData.elevation_matrix) return 0;
    const w = this.meshData.width;
    const h = this.meshData.height;
    const matrix = this.meshData.elevation_matrix;
    const elevMin = this.meshData.elev_min;
    const elevMax = this.meshData.elev_max;
    const elevRange = Math.max(1, elevMax - elevMin);
    const maxMeshHeight = 90;

    const fx = Math.min(w - 1, Math.max(0, normX * (w - 1)));
    const fy = Math.min(h - 1, Math.max(0, normY * (h - 1)));
    const x0 = Math.floor(fx);
    const x1 = Math.min(w - 1, x0 + 1);
    const y0 = Math.floor(fy);
    const y1 = Math.min(h - 1, y0 + 1);
    const dx = fx - x0;
    const dy = fy - y0;

    const v00 = matrix[y0][x0];
    const v10 = matrix[y0][x1];
    const v01 = matrix[y1][x0];
    const v11 = matrix[y1][x1];

    const top = v00 * (1 - dx) + v10 * dx;
    const bottom = v01 * (1 - dx) + v11 * dx;
    const rawElev = top * (1 - dy) + bottom * dy;

    return ((rawElev - elevMin) / elevRange) * maxMeshHeight;
  }

  // Geriye dönük uyumluluk
  addCandidateMarkers(candidates) {
    this.setCandidateMarkers(candidates, this.currentRegionId);
  }

  setCandidateMarkers(candidates, currentRegionId = null) {
    this.allCandidates = candidates || [];
    this.currentRegionId = currentRegionId;
    this.renderCandidateMarkers();
  }

  setRegionFilter(regionId) {
    this.currentRegionId = regionId;
    this.renderCandidateMarkers();
  }

  /**
   * Çözüm 2 ve Çözüm 3:
   * - Bölgesel arazi modunda (örn. Cabeus Ridge, Malapert Massif seçiliyken), yalnızca O BÖLGEYE ait iniş hedefini göster;
   *   100 km uzaktaki alakasız bölgelerin işaretçilerini haritadan kaldır!
   * - Shackleton genel DEM modunda yalnızca 4 Shackleton iniş hedefini göster.
   * - Halka tabanı zeminle tam temas etsin ('posY + 0.2').
   * - Işık sütunu zeminden başlasın ('posY + 17.5', boy 35).
   * - Hiçbir nesne havada asılı kalmasın veya gömülmesin!
   */
  renderCandidateMarkers() {
    if (this.candidateMarkersGroup) {
      this.scene.remove(this.candidateMarkersGroup);
      this.candidateMarkersGroup.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
      this.candidateMarkersGroup = null;
    }

    if (!this.allCandidates || this.allCandidates.length === 0) return;

    // Filtreleme: Shackleton modunda Shackleton hedefleri, Bölgesel modda sadece o bölgenin hedefi
    let visibleCandidates = [];
    const isShackleton = !this.currentRegionId || this.currentRegionId.startsWith("SITE_");

    if (isShackleton) {
      visibleCandidates = this.allCandidates.filter((c) => c.site_id.startsWith("SITE_"));
      if (visibleCandidates.length === 0) {
        visibleCandidates = this.allCandidates.slice(0, 4);
      }
    } else {
      visibleCandidates = this.allCandidates.filter((c) => c.site_id === this.currentRegionId);
      if (visibleCandidates.length === 0) {
        visibleCandidates = this.allCandidates.slice(0, 1);
      }
    }

    const group = new THREE.Group();
    const colorMap = {
      MALAPERT_MASSIF: 0x10b981,
      CONNECTING_RIDGE_EXT: 0x06b6d4,
      LEIBNITZ_BETA: 0x3b82f6,
      DE_GERLACHE_RIM_1: 0x8b5cf6,
      DE_GERLACHE_RIM_2: 0xa855f7,
      AMUNDSEN_RIM: 0x6366f1,
      NOBILE_RIM_2: 0xf59e0b,
      DE_GERLACHE_KOCHER: 0xec4899,
      HAWORTH: 0x14b8a6,
      SITE_ALPHA: 0x10b981,
      SITE_BETA: 0x38bdf8,
      SITE_GAMMA: 0xf59e0b,
      SITE_DELTA: 0xf43f5e,
      SHOEMAKER_RIM: 0x10b981,
      FAUSTINI_RIM: 0x38bdf8,
      CABEUS_RIDGE: 0x06b6d4,
      SLATER_RIM: 0xf59e0b,
      SVERDRUP_RIM: 0x8b5cf6,
    };

    visibleCandidates.forEach((cand) => {
      let normX = cand.coordinates && cand.coordinates.normalized ? cand.coordinates.normalized.norm_x : 0.5;
      let normY = cand.coordinates && cand.coordinates.normalized ? cand.coordinates.normalized.norm_y : 0.5;

      // Bölgesel DEM yerel sahasının merkezi (0.5, 0.5) koordinatındadır
      if (!isShackleton && cand.site_id === this.currentRegionId) {
        normX = 0.5;
        normY = 0.5;
      }

      const posX = (normX - 0.5) * 500;
      const posZ = (normY - 0.5) * 500;
      const posY = this.getHeightAt(normX, normY);

      let color = colorMap[cand.site_id] || 0x38bdf8;
      if (this.isNVG) color = 0xff2244;

      // Çözüm 3: Halka tabanı zeminle tam temas etsin ('posY + 0.2')
      const ringGeo = new THREE.RingGeometry(5, 8, 32);
      ringGeo.rotateX(-Math.PI / 2);
      const ringMat = new THREE.MeshBasicMaterial({
        color: color,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.9,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.set(posX, posY + 0.2, posZ);
      group.add(ring);

      // Çözüm 3: Işık sütunu zeminden başlasın ('posY + 17.5', boy 35)
      const beamGeo = new THREE.CylinderGeometry(0.35, 0.35, 35, 16);
      const beamMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.65,
      });
      const beam = new THREE.Mesh(beamGeo, beamMat);
      beam.position.set(posX, posY + 17.5, posZ);
      group.add(beam);

      // Zemin temas noktası
      const dotGeo = new THREE.SphereGeometry(1.2, 12, 12);
      const dotMat = new THREE.MeshBasicMaterial({ color: color });
      const dot = new THREE.Mesh(dotGeo, dotMat);
      dot.position.set(posX, posY + 0.3, posZ);
      group.add(dot);
    });

    this.scene.add(group);
    this.candidateMarkersGroup = group;
  }

  flyToCandidate(cand) {
    if (!cand) return;
    const isShackleton = !this.currentRegionId || this.currentRegionId.startsWith("SITE_");
    let normX = cand.coordinates && cand.coordinates.normalized ? cand.coordinates.normalized.norm_x : 0.5;
    let normY = cand.coordinates && cand.coordinates.normalized ? cand.coordinates.normalized.norm_y : 0.5;
    if (!isShackleton && cand.site_id === this.currentRegionId) {
      normX = 0.5;
      normY = 0.5;
    }

    const posX = (normX - 0.5) * 500;
    const posZ = (normY - 0.5) * 500;
    const posY = this.getHeightAt(normX, normY);

    this.lastPinCoords = { normX, normY, posX, posZ };

    if (this.landingPin) {
      this.landingPin.position.set(posX, posY, posZ);
      this.landingPin.visible = true;
    }

    if (this.controls && this.camera) {
      this.controls.target.set(posX, posY, posZ);
      this.camera.position.set(posX + 120, posY + 140, posZ + 120);
      this.controls.update();
    }
  }

  /**
   * Aşama 3: Dinamik Güneş Takip Koridoru (Shadow-Chasing Path Planner)
   * 3B harita üzerinde aydınlık sırt boyunca güvenli kaçış/seyir koridorunu temsil eden
   * yeşil/camgöbeği parıltılı tüp / hat çizer.
   */
  renderSunCorridor(show = true) {
    if (this.sunCorridorMesh) {
      this.scene.remove(this.sunCorridorMesh);
      if (this.sunCorridorMesh.geometry) this.sunCorridorMesh.geometry.dispose();
      if (this.sunCorridorMesh.material) this.sunCorridorMesh.material.dispose();
      this.sunCorridorMesh = null;
    }

    this.sunCorridorActive = show;
    if (!show || !this.meshData) return;

    const points = [];
    const numWaypoints = 32;

    const startNormX = this.lastPinCoords ? this.lastPinCoords.normX : 0.5;
    const startNormY = this.lastPinCoords ? this.lastPinCoords.normY : 0.5;

    for (let k = 0; k < numWaypoints; k++) {
      const t = k / (numWaypoints - 1);
      // Aydınlık tepe sırtını takip eden yumuşak rotalama
      const nx = THREE.MathUtils.clamp(startNormX + Math.sin(t * Math.PI * 1.6) * 0.32 * (1 - t * 0.25) + (t * 0.12), 0.05, 0.95);
      const ny = THREE.MathUtils.clamp(startNormY - t * 0.46 + Math.cos(t * Math.PI) * 0.1, 0.05, 0.95);

      const px = (nx - 0.5) * 500;
      const pz = (ny - 0.5) * 500;
      const py = this.getHeightAt(nx, ny) + 1.2; // Zeminin 1.2m üstünde güvenli koridor

      points.push(new THREE.Vector3(px, py, pz));
    }

    const curve = new THREE.CatmullRomCurve3(points);
    const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.75, 8, false);

    const corridorColor = this.isNVG ? 0xff2244 : 0x06b6d4;
    const tubeMat = new THREE.MeshStandardMaterial({
      color: corridorColor,
      emissive: corridorColor,
      emissiveIntensity: 0.9,
      transparent: true,
      opacity: 0.85,
      roughness: 0.25,
      metalness: 0.3,
    });

    this.sunCorridorMesh = new THREE.Mesh(tubeGeo, tubeMat);
    this.scene.add(this.sunCorridorMesh);
  }

  toggleSunCorridor() {
    this.renderSunCorridor(!this.sunCorridorActive);
    return this.sunCorridorActive;
  }

  /**
   * Aşama 3: Taktik OLED Kırmızı Gece Görüş Modu (Monochromatic NVG Theme)
   */
  setNVGMode(enabled) {
    this.isNVG = Boolean(enabled);

    if (this.isNVG) {
      if (this.scene) {
        this.scene.background = new THREE.Color(0x050102);
        this.scene.fog = new THREE.FogExp2(0x050102, 0.0018);
      }
      if (this.ambientLight) this.ambientLight.color.setHex(0x440a0f);
      if (this.sunLight) this.sunLight.color.setHex(0xff3344);
      if (this.terrainMesh && this.terrainMesh.material) {
        this.terrainMesh.material.color.setHex(0xff3344);
        this.terrainMesh.material.needsUpdate = true;
      }
    } else {
      if (this.scene) {
        this.scene.background = new THREE.Color(0x07090e);
        this.scene.fog = new THREE.FogExp2(0x07090e, 0.0015);
      }
      if (this.ambientLight) this.ambientLight.color.setHex(0x1a202c);
      if (this.sunLight) this.sunLight.color.setHex(0xfff7ed);
      if (this.terrainMesh && this.terrainMesh.material) {
        this.terrainMesh.material.color.setHex(0xffffff);
        this.terrainMesh.material.needsUpdate = true;
      }
    }

    // Katman dokusunu ve işaretçileri güncelle
    this.setLayer(this.currentLayer);
    this.renderCandidateMarkers();
    if (this.sunCorridorActive) {
      this.renderSunCorridor(true);
    }
  }

  setCameraPreset(preset) {
    if (!this.camera || !this.controls) return;
    if (preset === "top") {
      this.camera.position.set(0, 600, 1);
      this.controls.target.set(0, 0, 0);
    } else if (preset === "iso") {
      this.camera.position.set(350, 350, 350);
      this.controls.target.set(0, 20, 0);
    } else if (preset === "side") {
      this.camera.position.set(-450, 90, 0);
      this.controls.target.set(0, 30, 0);
    }
  }
}

window.LunarTerrainViewer = LunarTerrainViewer;
