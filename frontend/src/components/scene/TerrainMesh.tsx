import React, { useMemo, useState, useEffect } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import { useMission } from '../../context/MissionContext';
import { assetUrl } from '../../services/assetUrl';

export const TerrainMesh: React.FC = () => {
  const { siteId, terrainData, isVirtualPatchApplied, isCaseActive, activePoint } = useMission();

  const [terrainTexture, setTerrainTexture] = useState<THREE.Texture | null>(null);
  const [terrainNormal, setTerrainNormal] = useState<THREE.Texture | null>(null);

  // Load site-specific photorealistic texture and normal maps generated directly from 5m/px LOLA GeoTIFF
  useEffect(() => {
    const loader = new THREE.TextureLoader();
    const texFile = siteId === 'Site04' 
      ? assetUrl('textures/terrain_site04_texture.jpg') 
      : assetUrl('textures/terrain_site01_texture.jpg');
    const normFile = siteId === 'Site04' 
      ? assetUrl('textures/terrain_site04_normal.jpg') 
      : assetUrl('textures/terrain_site01_normal.jpg');

    loader.load(texFile, (t) => {
      t.wrapS = THREE.ClampToEdgeWrapping;
      t.wrapT = THREE.ClampToEdgeWrapping;
      t.colorSpace = THREE.SRGBColorSpace;
      t.minFilter = THREE.LinearMipmapLinearFilter;
      t.magFilter = THREE.LinearFilter;
      t.needsUpdate = true;
      setTerrainTexture(t);
    });

    loader.load(normFile, (t) => {
      t.wrapS = THREE.ClampToEdgeWrapping;
      t.wrapT = THREE.ClampToEdgeWrapping;
      t.minFilter = THREE.LinearMipmapLinearFilter;
      t.magFilter = THREE.LinearFilter;
      t.needsUpdate = true;
      setTerrainNormal(t);
    });
  }, [siteId]);

  if (!terrainData) return null;

  const { bounds, grid_size, observer_pos, patch_center_m, rays } = terrainData;
  const [rows, cols] = grid_size;

  const obsX = observer_pos.x_m;
  const obsY = observer_pos.y_m;
  const obsZGround = observer_pos.z_ground_m;

  // Grid x ve y koordinat sınırları (gözlemciye göre)
  const minX = bounds.min_x - obsX;
  const maxX = bounds.max_x - obsX;
  const minY = bounds.min_y - obsY;
  const maxY = bounds.max_y - obsY;

  // Helper: Grid koordinatlarından zemin yüksekliğini enterpole etme
  const getElevationAt = (relX: number, relY: number): number => {
    const u = THREE.MathUtils.clamp((relX - minX) / (maxX - minX), 0, 1);
    const v = THREE.MathUtils.clamp((maxY - relY) / (maxY - minY), 0, 1);
    const c = Math.min(cols - 1, Math.max(0, Math.round(u * (cols - 1))));
    const r = Math.min(rows - 1, Math.max(0, Math.round(v * (rows - 1))));
    return (terrainData.elevations_surf[r]?.[c] ?? obsZGround) - obsZGround;
  };

  // 1. 8 km x 8 km Gerçek LOLA Arazi BufferGeometry ve Katı Etek (Skirt)
  const { terrainGeometry, skirtGeometry, minRelElevation } = useMemo(() => {
    const geo = new THREE.PlaneGeometry(
      bounds.width_m,
      bounds.height_m,
      cols - 1,
      rows - 1
    );
    geo.rotateX(-Math.PI / 2);

    const posAttr = geo.attributes.position;
    const vertexCount = posAttr.count;
    const colors = new Float32Array(vertexCount * 3);

    // Yama sınırları (göreli)
    const patchMinX = patch_center_m.x_m - 200 - obsX;
    const patchMaxX = patch_center_m.x_m + 200 - obsX;
    const patchMinY = patch_center_m.y_m - 200 - obsY;
    const patchMaxY = patch_center_m.y_m + 200 - obsY;

    let lowestRelZ = 0;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        let z = terrainData.elevations_surf[r][c];

        // Sanal yama uygulandığında hata rasterı eklenir
        if (isVirtualPatchApplied && isCaseActive && terrainData.elevations_err_clone1) {
          z += terrainData.elevations_err_clone1[r][c];
        }

        const relZ = z - obsZGround;
        if (relZ < lowestRelZ) lowestRelZ = relZ;

        const relX = minX + (c / (cols - 1)) * (maxX - minX);
        const relY = maxY - (r / (rows - 1)) * (maxY - minY);

        posAttr.setXYZ(idx, relX, relZ, -relY);

        // Sanal yama aktifse sadece o alanı amber ile hafif vurgula; aksi halde doğal ay rengi (1.0, 1.0, 1.0)
        const isInsidePatch =
          relX >= patchMinX && relX <= patchMaxX && relY >= patchMinY && relY <= patchMaxY;

        if (isInsidePatch && isVirtualPatchApplied) {
          colors[idx * 3] = 1.0;
          colors[idx * 3 + 1] = 0.78;
          colors[idx * 3 + 2] = 0.35;
        } else {
          // Doğal PBR kaplamanın tüm detaylarını sergilemek için nötr beyaz
          colors[idx * 3] = 1.0;
          colors[idx * 3 + 1] = 1.0;
          colors[idx * 3 + 2] = 1.0;
        }
      }
    }

    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();

    // Jeolojik Katı Etek (Skirt): Modelin kenarlarından aşağı inen katı yan duvarlar
    const skirtBaseY = lowestRelZ - 150;
    const skirtVertices: number[] = [];
    const skirtIndices: number[] = [];
    let vertOffset = 0;

    const addSkirtWall = (pointsTop: THREE.Vector3[]) => {
      for (let i = 0; i < pointsTop.length - 1; i++) {
        const p1 = pointsTop[i];
        const p2 = pointsTop[i + 1];
        const b1 = new THREE.Vector3(p1.x, skirtBaseY, p1.z);
        const b2 = new THREE.Vector3(p2.x, skirtBaseY, p2.z);

        skirtVertices.push(
          p1.x, p1.y, p1.z,
          p2.x, p2.y, p2.z,
          b2.x, b2.y, b2.z,
          b1.x, b1.y, b1.z
        );

        skirtIndices.push(
          vertOffset, vertOffset + 1, vertOffset + 2,
          vertOffset, vertOffset + 2, vertOffset + 3
        );
        vertOffset += 4;
      }
    };

    // Kuzey kenarı (r = 0)
    const northTop: THREE.Vector3[] = [];
    for (let c = 0; c < cols; c++) {
      const v = new THREE.Vector3();
      v.fromBufferAttribute(posAttr, c);
      northTop.push(v);
    }
    addSkirtWall(northTop);

    // Doğu kenarı (c = cols - 1)
    const eastTop: THREE.Vector3[] = [];
    for (let r = 0; r < rows; r++) {
      const v = new THREE.Vector3();
      v.fromBufferAttribute(posAttr, r * cols + (cols - 1));
      eastTop.push(v);
    }
    addSkirtWall(eastTop);

    // Güney kenarı (r = rows - 1)
    const southTop: THREE.Vector3[] = [];
    for (let c = cols - 1; c >= 0; c--) {
      const v = new THREE.Vector3();
      v.fromBufferAttribute(posAttr, (rows - 1) * cols + c);
      southTop.push(v);
    }
    addSkirtWall(southTop);

    // Batı kenarı (c = 0)
    const westTop: THREE.Vector3[] = [];
    for (let r = rows - 1; r >= 0; r--) {
      const v = new THREE.Vector3();
      v.fromBufferAttribute(posAttr, r * cols);
      westTop.push(v);
    }
    addSkirtWall(westTop);

    const skirtGeo = new THREE.BufferGeometry();
    skirtGeo.setAttribute('position', new THREE.Float32BufferAttribute(skirtVertices, 3));
    skirtGeo.setIndex(skirtIndices);
    skirtGeo.computeVertexNormals();

    return { terrainGeometry: geo, skirtGeometry: skirtGeo, minRelElevation: lowestRelZ };
  }, [terrainData, isVirtualPatchApplied, isCaseActive, obsX, obsY, obsZGround, minX, maxX, minY, maxY, rows, cols]);

  // 2. 400x400m Görev Ölçüm Alanı Sınır Çizgisi (Topografyaya mükemmel oturan hat)
  const patchLineGeometry = useMemo(() => {
    const points: THREE.Vector3[] = [];
    const pMinX = patch_center_m.x_m - 200 - obsX;
    const pMaxX = patch_center_m.x_m + 200 - obsX;
    const pMinY = patch_center_m.y_m - 200 - obsY;
    const pMaxY = patch_center_m.y_m + 200 - obsY;

    const segments = 16;
    // Alt kenar: (minX, minY) -> (maxX, minY)
    for (let i = 0; i <= segments; i++) {
      const x = pMinX + (i / segments) * (pMaxX - pMinX);
      const y = pMinY;
      const z = getElevationAt(x, y) + 2.5;
      points.push(new THREE.Vector3(x, z, -y));
    }
    // Sağ kenar: (maxX, minY) -> (maxX, maxY)
    for (let i = 1; i <= segments; i++) {
      const x = pMaxX;
      const y = pMinY + (i / segments) * (pMaxY - pMinY);
      const z = getElevationAt(x, y) + 2.5;
      points.push(new THREE.Vector3(x, z, -y));
    }
    // Üst kenar: (maxX, maxY) -> (minX, maxY)
    for (let i = 1; i <= segments; i++) {
      const x = pMaxX - (i / segments) * (pMaxX - pMinX);
      const y = pMaxY;
      const z = getElevationAt(x, y) + 2.5;
      points.push(new THREE.Vector3(x, z, -y));
    }
    // Sol kenar: (minX, maxY) -> (minX, minY)
    for (let i = 1; i < segments; i++) {
      const x = pMinX;
      const y = pMaxY - (i / segments) * (pMaxY - pMinY);
      const z = getElevationAt(x, y) + 2.5;
      points.push(new THREE.Vector3(x, z, -y));
    }

    return new THREE.BufferGeometry().setFromPoints(points);
  }, [patch_center_m, obsX, obsY, getElevationAt]);

  // 3. Işınlar: Dünya, Güneş, 130° ve 131° Ufuk Belirleyici Işınlar
  const hasSpecificRays = !!(rays && rays.ray_130 && rays.ray_131 && rays.earth_ray);

  const occluder130Rel = useMemo(() => {
    if (!hasSpecificRays || !rays?.ray_130?.occluder_coords) return null;
    const coords = rays.ray_130.occluder_coords;
    return new THREE.Vector3(coords.x_m - obsX, coords.z_m - obsZGround, -(coords.y_m - obsY));
  }, [hasSpecificRays, rays, obsX, obsY, obsZGround]);

  const occluder131Rel = useMemo(() => {
    if (!hasSpecificRays || !rays?.ray_131?.occluder_coords) return null;
    const coords = rays.ray_131.occluder_coords;
    return new THREE.Vector3(coords.x_m - obsX, coords.z_m - obsZGround, -(coords.y_m - obsY));
  }, [hasSpecificRays, rays, obsX, obsY, obsZGround]);

  // Gerçek Ephemeris Zamanına Göre Güneş Vektörü ve Dinamik Güneş Işığı
  const sunPosition = useMemo(() => {
    const az = (hasSpecificRays && isCaseActive) ? 206.822286 : activePoint.sunAz;
    const alt = (hasSpecificRays && isCaseActive) ? 1.069834 : activePoint.sunAlt;
    const azRad = (az * Math.PI) / 180;
    const altRad = (alt * Math.PI) / 180;
    const dist = 3200;
    const dx = dist * Math.cos(altRad) * Math.sin(azRad);
    const dy = dist * Math.sin(altRad);
    const dz = -dist * Math.cos(altRad) * Math.cos(azRad);
    return new THREE.Vector3(dx, 2.0 + dy, dz);
  }, [hasSpecificRays, isCaseActive, activePoint.sunAz, activePoint.sunAlt]);

  // Dünya Vektörü: Gözlemci göz seviyesinden (0, 2, 0)
  const earthRayEnd = useMemo(() => {
    const az = (hasSpecificRays && isCaseActive && rays?.earth_ray) ? rays.earth_ray.azimuth_deg : activePoint.earthAz;
    const alt = (hasSpecificRays && isCaseActive && rays?.earth_ray) ? rays.earth_ray.altitude_deg : activePoint.earthAlt;
    const azRad = (az * Math.PI) / 180;
    const altRad = (alt * Math.PI) / 180;
    const dist = 2800;
    const dx = dist * Math.cos(altRad) * Math.sin(azRad);
    const dy = dist * Math.sin(altRad);
    const dz = -dist * Math.cos(altRad) * Math.cos(azRad);
    return new THREE.Vector3(dx, 2.0 + dy, dz);
  }, [hasSpecificRays, isCaseActive, rays, activePoint.earthAz, activePoint.earthAlt]);

  const patchCenterElevation = getElevationAt(patch_center_m.x_m - obsX, patch_center_m.y_m - obsY);

  return (
    <group>
      {/* Gerçek Güneş Ephemeris Doğrultusunda Dinamik Güneş Işığı */}
      <directionalLight
        position={sunPosition}
        intensity={2.8}
        color="#fffbeb"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-4200}
        shadow-camera-right={4200}
        shadow-camera-top={4200}
        shadow-camera-bottom={-4200}
        shadow-camera-near={10}
        shadow-camera-far={8000}
      />

      {/* 3B Gerçek Ay Yüzeyi: NASA LOLA 5m/px Sayısal Yükseklik Modeli */}
      <mesh geometry={terrainGeometry} receiveShadow castShadow>
        <meshStandardMaterial
          map={terrainTexture || undefined}
          normalMap={terrainNormal || undefined}
          normalScale={new THREE.Vector2(2.5, 2.5)}
          vertexColors
          roughness={0.88}
          metalness={0.05}
          wireframe={false}
          flatShading={false}
        />
      </mesh>

      {/* Jeolojik Katı Taban Eteği (Blok Model Görünümü) */}
      <mesh geometry={skirtGeometry} receiveShadow>
        <meshStandardMaterial
          color="#151e2d"
          roughness={0.92}
          metalness={0.08}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Gözlemci Direği (2m Göz İrtifası) */}
      <group position={[0, 0, 0]}>
        {/* Direk */}
        <mesh position={[0, 4.0, 0]}>
          <cylinderGeometry args={[0.6, 0.6, 8.0, 16]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.9} roughness={0.15} />
        </mesh>
        {/* Kamera Sensörü */}
        <mesh position={[0, 8.0, 0]}>
          <sphereGeometry args={[1.5, 16, 16]} />
          <meshStandardMaterial color="#38bdf8" emissive="#0284c7" emissiveIntensity={1.2} />
        </mesh>
        <Html position={[0, 14.0, 0]} center distanceFactor={140} zIndexRange={[1, 0]}>
          <div className="px-2 py-0.5 rounded bg-space-950/95 text-sky-300 border border-sky-400 text-[10px] font-mono font-bold whitespace-nowrap shadow-xl pointer-events-none flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></span>
            <span>Gözlemci İstasyonu ({obsZGround.toFixed(0)} m)</span>
          </div>
        </Html>
      </group>

      {/* 400x400m Görev Ölçüm Alanı Sınır Çizgisi */}
      <lineLoop geometry={patchLineGeometry}>
        <lineBasicMaterial
          color={isVirtualPatchApplied ? '#f59e0b' : '#38bdf8'}
          linewidth={3}
          transparent
          opacity={0.9}
        />
      </lineLoop>

      {/* Ölçüm Alanı Merkez Rozeti */}
      <group position={[patch_center_m.x_m - obsX, patchCenterElevation + 18.0, -(patch_center_m.y_m - obsY)]}>
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([new THREE.Vector3(0, -16, 0), new THREE.Vector3(0, 0, 0)]);
            }}
          />
          <lineBasicMaterial color="#f59e0b" transparent opacity={0.65} />
        </line>
        <Html center distanceFactor={180} zIndexRange={[1, 0]}>
          <div className="px-2.5 py-1 rounded-full bg-space-950/95 text-amber-300 border border-amber-500 text-[10px] font-mono font-bold whitespace-nowrap shadow-xl flex items-center gap-1.5 pointer-events-none">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
            <span>400×400 m Ölçüm Alanı ({siteId})</span>
          </div>
        </Html>
      </group>

      {/* Bölgesel Coğrafi İşaretler (Site01: Connecting Ridge / Site04: Shackleton) */}
      {siteId === 'Site01' ? (
        <group position={[-1800, 10, -2200]}>
          <Html center distanceFactor={260} zIndexRange={[1, 0]}>
            <div className="px-2 py-0.5 rounded bg-slate-950/90 text-slate-300 border border-slate-700 text-[10px] font-mono whitespace-nowrap shadow-lg pointer-events-none">
              Connecting Ridge Sırt Hattı (Zirve: +1959 m)
            </div>
          </Html>
        </group>
      ) : (
        <>
          <group position={[1200, -800, 1600]}>
            <Html center distanceFactor={260} zIndexRange={[1, 0]}>
              <div className="px-2 py-0.5 rounded bg-red-950/90 text-red-300 border border-red-700/80 text-[10px] font-mono whitespace-nowrap shadow-lg pointer-events-none">
                Shackleton Krater Çukuru (-1730 m)
              </div>
            </Html>
          </group>
          <group position={[-1400, 600, -1200]}>
            <Html center distanceFactor={260} zIndexRange={[1, 0]}>
              <div className="px-2 py-0.5 rounded bg-emerald-950/90 text-emerald-300 border border-emerald-700/80 text-[10px] font-mono whitespace-nowrap shadow-lg pointer-events-none">
                Shackleton Kenar Sırt Zirvesi (+1739 m)
              </div>
            </Html>
          </group>
        </>
      )}

      {/* 130° ve 131° Ufuk Belirleyici Işınlar */}
      {occluder130Rel && (
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([new THREE.Vector3(0, 2.0, 0), occluder130Rel]);
            }}
          />
          <lineBasicMaterial color="#a855f7" transparent opacity={0.65} linewidth={2} />
        </line>
      )}

      {occluder131Rel && (
        <>
          <line>
            <bufferGeometry
              attach="geometry"
              onUpdate={(self) => {
                self.setFromPoints([new THREE.Vector3(0, 2.0, 0), occluder131Rel]);
              }}
            />
            <lineBasicMaterial color="#10b981" transparent opacity={0.85} linewidth={2} />
          </line>

          <group position={occluder131Rel}>
            <mesh>
              <sphereGeometry args={[1.5, 16, 16]} />
              <meshStandardMaterial
                color="#ef4444"
                emissive="#dc2626"
                emissiveIntensity={1.0}
              />
            </mesh>
            <Html position={[0, 4.0, 0]} center distanceFactor={80} zIndexRange={[1, 0]}>
              <div className="px-1.5 py-0.5 rounded bg-red-950/90 text-red-300 border border-red-500/60 text-[9px] font-mono whitespace-nowrap pointer-events-none shadow-sm">
                Kritik Sırt Engeli (80 m, Az: 131°)
              </div>
            </Html>
          </group>
        </>
      )}

      {/* Dünya Görüş Hattı (Buz Mavisi) */}
      <line>
        <bufferGeometry
          attach="geometry"
          onUpdate={(self) => {
            self.setFromPoints([new THREE.Vector3(0, 2.0, 0), earthRayEnd]);
          }}
        />
        <lineBasicMaterial color="#38bdf8" linewidth={3} />
      </line>

      {/* Dünya Hedef Küresi (Görüş Hattı Ucunda) */}
      <group position={earthRayEnd}>
        <mesh>
          <sphereGeometry args={[35, 32, 32]} />
          <meshStandardMaterial
            color="#38bdf8"
            emissive="#0284c7"
            emissiveIntensity={1.2}
            roughness={0.2}
          />
        </mesh>
        <Html position={[0, 45, 0]} center distanceFactor={260} zIndexRange={[1, 0]}>
          <div className="px-2.5 py-1 rounded bg-sky-950/95 text-sky-200 border border-sky-400 text-[10px] font-mono font-bold whitespace-nowrap shadow-xl pointer-events-none">
            Dünya (Yükseklik: {activePoint.earthAlt.toFixed(2)}°, Azimut: {activePoint.earthAz.toFixed(1)}°)
          </div>
        </Html>
      </group>

      {/* Güneş Hedef Küresi */}
      <group position={sunPosition}>
        <mesh>
          <sphereGeometry args={[45, 32, 32]} />
          <meshBasicMaterial color="#fbbf24" />
        </mesh>
        <Html position={[0, 55, 0]} center distanceFactor={260} zIndexRange={[1, 0]}>
          <div className="px-2.5 py-1 rounded bg-amber-950/95 text-amber-200 border border-amber-400 text-[10px] font-mono font-bold whitespace-nowrap shadow-xl pointer-events-none">
            Güneş (Yükseklik: {activePoint.sunAlt.toFixed(2)}°, Azimut: {activePoint.sunAz.toFixed(1)}°)
          </div>
        </Html>
      </group>
    </group>
  );
};
