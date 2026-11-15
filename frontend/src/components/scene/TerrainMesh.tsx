import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import { useMission } from '../../context/MissionContext';

export const TerrainMesh: React.FC = () => {
  const { terrainData, isVirtualPatchApplied, isCaseActive, activePoint } = useMission();

  if (!terrainData) return null;

  const { bounds, grid_size, resolution_m, observer_pos, patch_corners_m, patch_center_m, rays } = terrainData;
  const [rows, cols] = grid_size;

  // Gözlemciyi (0, 0) kabul ederek göreli koordinatlara dönüştürelim
  // X: Easting, Y: Northing, Z: Elevation
  const obsX = observer_pos.x_m;
  const obsY = observer_pos.y_m;
  const obsZGround = observer_pos.z_ground_m;
  const obsZEye = observer_pos.z_eye_m;

  // 1. Arazi BufferGeometry oluşturma
  const terrainGeometry = useMemo(() => {
    const geo = new THREE.PlaneGeometry(
      bounds.width_m,
      bounds.height_m,
      cols - 1,
      rows - 1
    );

    // PlaneGeometry varsayılan olarak XY düzlemindedir; XZ düzlemine çevirelim
    geo.rotateX(-Math.PI / 2);

    const posAttr = geo.attributes.position;
    const vertexCount = posAttr.count;

    // Renk attribute'u: yama alanını ve yükseklik farkını renklendirmek için
    const colors = new Float32Array(vertexCount * 3);

    // Grid x ve y koordinat aralıkları
    const minX = bounds.min_x - obsX;
    const maxX = bounds.max_x - obsX;
    const minY = bounds.min_y - obsY;
    const maxY = bounds.max_y - obsY;

    // Yama sınırları (göreli)
    const patchMinX = patch_center_m.x_m - 200 - obsX;
    const patchMaxX = patch_center_m.x_m + 200 - obsX;
    const patchMinY = patch_center_m.y_m - 200 - obsY;
    const patchMaxY = patch_center_m.y_m + 200 - obsY;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        
        let z = terrainData.elevations_surf[r][c];

        // Sanal yama uygulandığında hata rasterı (Clone 1) eklenir
        if (isVirtualPatchApplied && isCaseActive && terrainData.elevations_err_clone1) {
          const err = terrainData.elevations_err_clone1[r][c];
          z += err;
        }

        // Göreli yükseklik (gözlemci zeminine göre)
        const relZ = z - obsZGround;
        
        // Üçgen vertex pozisyonu: X = relX, Y = relZ, Z = -relY (Three.js koordinat sistemi: Z geriye doğru)
        const relX = minX + (c / (cols - 1)) * (maxX - minX);
        const relY = maxY - (r / (rows - 1)) * (maxY - minY);

        posAttr.setXYZ(idx, relX, relZ, -relY);

        // Renklendirme
        const isInsidePatch =
          relX >= patchMinX && relX <= patchMaxX && relY >= patchMinY && relY <= patchMaxY;

        if (isInsidePatch) {
          if (isVirtualPatchApplied) {
            // Sanal yama aktif: amber / turuncu tonu
            colors[idx * 3] = 0.95;
            colors[idx * 3 + 1] = 0.65;
            colors[idx * 3 + 2] = 0.2;
          } else {
            // Ölçüm alanı hedefi: açık mavi / morumsu ton
            colors[idx * 3] = 0.35;
            colors[idx * 3 + 1] = 0.55;
            colors[idx * 3 + 2] = 0.85;
          }
        } else {
          // Normal ay regoliti: gri varyasyonu
          const gray = THREE.MathUtils.clamp(0.25 + (relZ / 10.0) * 0.1, 0.15, 0.5);
          colors[idx * 3] = gray;
          colors[idx * 3 + 1] = gray;
          colors[idx * 3 + 2] = gray * 1.05;
        }
      }
    }

    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    return geo;
  }, [terrainData, isVirtualPatchApplied, isCaseActive, obsX, obsY, obsZGround]);

  // 2. Ölçüm Alanı 400x400m Poligon Sınır Çizgisi
  const patchLineGeometry = useMemo(() => {
    const points: THREE.Vector3[] = [];
    patch_corners_m.forEach((corner) => {
      const px = corner.x_m - obsX;
      const py = corner.y_m - obsY;
      // Yükseklik: biraz havada (araziye gömülmemesi için +1.5m)
      points.push(new THREE.Vector3(px, 3.5, -py));
    });
    // Kapat
    const first = patch_corners_m[0];
    points.push(new THREE.Vector3(first.x_m - obsX, 3.5, -first.y_m - obsY));

    const geo = new THREE.BufferGeometry().setFromPoints(points);
    return geo;
  }, [patch_corners_m, obsX, obsY]);

  // 3. Işınlar: Dünya, Güneş, 130° ve 131° Ufuk Belirleyici Işınlar
  const hasSpecificRays = !!(rays && rays.ray_130 && rays.ray_131 && rays.earth_ray);

  // 130° Engel: 80m mesafede
  const occluder130Rel = useMemo(() => {
    if (!hasSpecificRays || !rays?.ray_130?.occluder_coords) return null;
    const coords = rays.ray_130.occluder_coords;
    return new THREE.Vector3(coords.x_m - obsX, coords.z_m - obsZGround, -(coords.y_m - obsY));
  }, [hasSpecificRays, rays, obsX, obsY, obsZGround]);

  // 131° Engel (Baskın engel hücresi: 80m)
  const occluder131Rel = useMemo(() => {
    if (!hasSpecificRays || !rays?.ray_131?.occluder_coords) return null;
    const coords = rays.ray_131.occluder_coords;
    return new THREE.Vector3(coords.x_m - obsX, coords.z_m - obsZGround, -(coords.y_m - obsY));
  }, [hasSpecificRays, rays, obsX, obsY, obsZGround]);

  // Dünya Vektörü: Gözlemci göz seviyesinden (0, 2, 0)
  const earthRayEnd = useMemo(() => {
    const az = (hasSpecificRays && isCaseActive && rays?.earth_ray) ? rays.earth_ray.azimuth_deg : activePoint.earthAz;
    const alt = (hasSpecificRays && isCaseActive && rays?.earth_ray) ? rays.earth_ray.altitude_deg : activePoint.earthAlt;
    const azRad = (az * Math.PI) / 180;
    const altRad = (alt * Math.PI) / 180;
    const dist = 300;
    const dx = dist * Math.cos(altRad) * Math.sin(azRad);
    const dy = dist * Math.sin(altRad);
    const dz = -dist * Math.cos(altRad) * Math.cos(azRad);
    return new THREE.Vector3(dx, 2.0 + dy, dz);
  }, [hasSpecificRays, isCaseActive, rays, activePoint.earthAz, activePoint.earthAlt]);

  // Güneş Vektörü
  const sunRayEnd = useMemo(() => {
    const az = (hasSpecificRays && isCaseActive) ? 206.822286 : activePoint.sunAz;
    const alt = (hasSpecificRays && isCaseActive) ? 1.069834 : activePoint.sunAlt;
    const azRad = (az * Math.PI) / 180;
    const altRad = (alt * Math.PI) / 180;
    const dist = 280;
    const dx = dist * Math.cos(altRad) * Math.sin(azRad);
    const dy = dist * Math.sin(altRad);
    const dz = -dist * Math.cos(altRad) * Math.cos(azRad);
    return new THREE.Vector3(dx, 2.0 + dy, dz);
  }, [hasSpecificRays, isCaseActive, activePoint.sunAz, activePoint.sunAlt]);

  return (
    <group>
      {/* 3B Arazi Yüzeyi */}
      <mesh geometry={terrainGeometry} receiveShadow castShadow>
        <meshStandardMaterial
          vertexColors
          roughness={0.85}
          metalness={0.15}
          wireframe={false}
          flatShading={false}
        />
      </mesh>

      {/* Geometrik Ufuk Referans Çemberi (0° Düzlemi, Göz Seviyesinde) */}
      <mesh position={[0, 2.0, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[120, 120.5, 64]} />
        <meshBasicMaterial color="#64748b" transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>

      {/* Gözlemci Direği (2m Göz İrtifası) */}
      <group position={[0, 0, 0]}>
        {/* Direk */}
        <mesh position={[0, 1.0, 0]}>
          <cylinderGeometry args={[0.08, 0.08, 2.0, 16]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.8} roughness={0.2} />
        </mesh>
        {/* Kamera Sensörü */}
        <mesh position={[0, 2.0, 0]}>
          <sphereGeometry args={[0.2, 16, 16]} />
          <meshStandardMaterial color="#38bdf8" emissive="#0284c7" emissiveIntensity={0.6} />
        </mesh>
        <Html position={[0, 2.5, 0]} center distanceFactor={35} zIndexRange={[1, 0]}>
          <div className="px-1.5 py-0.5 rounded bg-space-950/90 text-sky-300 border border-sky-500/50 text-[9px] font-mono whitespace-nowrap shadow-md pointer-events-none">
            Gözlemci (h=2m)
          </div>
        </Html>
      </group>

      {/* 400x400m Ölçüm Alanı Sınır Çizgisi (Target_MethodA_CriticalRidge) */}
      <lineLoop geometry={patchLineGeometry}>
        <lineBasicMaterial
          color={isVirtualPatchApplied ? '#f59e0b' : '#38bdf8'}
          linewidth={2}
          transparent
          opacity={0.85}
        />
      </lineLoop>

      {/* Ölçüm Alanı Merkez Etiketi (Kritik engelden ayrılmış, yüksek irtifalı ve lider çizgili) */}
      <group position={[patch_center_m.x_m - obsX, 14.0, -(patch_center_m.y_m - obsY)]}>
        {/* Lider Çizgisi (Zeminden etikete) */}
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([new THREE.Vector3(0, -12, 0), new THREE.Vector3(0, 0, 0)]);
            }}
          />
          <lineDashedMaterial color="#f59e0b" dashSize={1} gapSize={0.5} transparent opacity={0.6} />
        </line>
        <Html center distanceFactor={55} zIndexRange={[1, 0]}>
          <div className="px-2 py-0.5 rounded-full bg-space-950/95 text-amber-300 border border-amber-500/60 text-[9px] font-mono whitespace-nowrap shadow-md flex items-center gap-1.5 pointer-events-none">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span>
            <span>400×400 m Ölçüm Alanı</span>
          </div>
        </Html>
      </group>

      {/* 130° ve 131° Ufuk Belirleyici Işınlar */}
      {/* 130° Işını */}
      {occluder130Rel && (
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([new THREE.Vector3(0, 2.0, 0), occluder130Rel]);
            }}
          />
          <lineBasicMaterial color="#a855f7" transparent opacity={0.6} />
        </line>
      )}

      {/* 131° Işını (Baskın Engel) */}
      {occluder131Rel && (
        <>
          <line>
            <bufferGeometry
              attach="geometry"
              onUpdate={(self) => {
                self.setFromPoints([new THREE.Vector3(0, 2.0, 0), occluder131Rel]);
              }}
            />
            <lineBasicMaterial color="#10b981" transparent opacity={0.8} />
          </line>

          {/* Temsilî Engel Sırtı Hücresi (80m) */}
          <group position={occluder131Rel}>
            <mesh>
              <sphereGeometry args={[0.6, 16, 16]} />
              <meshStandardMaterial
                color="#ef4444"
                emissive="#dc2626"
                emissiveIntensity={0.8}
              />
            </mesh>
            <Html position={[0, 1.8, 0]} center distanceFactor={40} zIndexRange={[1, 0]}>
              <div className="px-1.5 py-0.5 rounded bg-red-950/90 text-red-300 border border-red-500/60 text-[9px] font-mono whitespace-nowrap pointer-events-none shadow-sm">
                Kritik Sırt Engeli (80 m, Az: 131°)
              </div>
            </Html>
          </group>
        </>
      )}

      {/* Dünya Görüş Çizgisi (Buz Mavisi) */}
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
          <sphereGeometry args={[3.5, 32, 32]} />
          <meshStandardMaterial
            color="#38bdf8"
            emissive="#0284c7"
            emissiveIntensity={0.9}
            roughness={0.2}
          />
        </mesh>
        <Html position={[0, 4.5, 0]} center distanceFactor={65} zIndexRange={[1, 0]}>
          <div className="px-2 py-0.5 rounded bg-sky-950/90 text-sky-300 border border-sky-400 text-[9px] font-mono font-bold whitespace-nowrap shadow-md pointer-events-none">
            Dünya ({activePoint.earthAlt.toFixed(2)}°, Az: {activePoint.earthAz.toFixed(1)}°)
          </div>
        </Html>
      </group>

      {/* Güneş Görüş Çizgisi (Sıcak Sarı) */}
      <line>
        <bufferGeometry
          attach="geometry"
          onUpdate={(self) => {
            self.setFromPoints([new THREE.Vector3(0, 2.0, 0), sunRayEnd]);
          }}
        />
        <lineBasicMaterial color="#fbbf24" linewidth={2} transparent opacity={0.7} />
      </line>

      {/* Güneş Hedef Küresi */}
      <group position={sunRayEnd}>
        <mesh>
          <sphereGeometry args={[4.5, 32, 32]} />
          <meshBasicMaterial color="#fbbf24" />
        </mesh>
        <Html position={[0, 5.5, 0]} center distanceFactor={65} zIndexRange={[1, 0]}>
          <div className="px-2 py-0.5 rounded bg-amber-950/90 text-amber-300 border border-amber-400 text-[9px] font-mono font-bold whitespace-nowrap shadow-md pointer-events-none">
            Güneş ({activePoint.sunAlt.toFixed(2)}°, Az: {activePoint.sunAz.toFixed(1)}°)
          </div>
        </Html>
      </group>
    </group>
  );
};
