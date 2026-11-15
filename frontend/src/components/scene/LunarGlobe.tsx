import { assetUrl } from '../../services/assetUrl';
import React, { useRef, useMemo, useState, useEffect } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { useMission } from '../../context/MissionContext';
import { SITES } from '../../services/dataService';
import { SiteId } from '../../types';

/**
 * Three.js SphereGeometry ile %100 matematiksel olarak eşleşen Enlem/Boylam dönüşümü.
 * Moon Trek Equirectangular:
 *  - Enlem: +90° (Kuzey, Y=+R, V=0) -> -90° (Güney, Y=-R, V=1)
 *  - Boylam: -180° (Sol, U=0) -> 0° (Merkez, U=0.5) -> +180° (Sağ, U=1)
 */
function latLonToVector3(latDeg: number, lonEastDeg: number, radius: number): THREE.Vector3 {
  const phi = (90 - latDeg) * (Math.PI / 180); // 0 (Kuzey) to PI (Güney)
  const theta = (lonEastDeg + 180) * (Math.PI / 180); // 0 to 2*PI

  // Three.js standart SphereGeometry vertex parametrizasyonu:
  const x = -radius * Math.cos(theta) * Math.sin(phi);
  const y = radius * Math.cos(phi);
  const z = radius * Math.sin(theta) * Math.sin(phi);

  return new THREE.Vector3(x, y, z);
}

export const LunarGlobe: React.FC = () => {
  const { siteId, setSiteId, setCameraMode, layerMode, displacementEnabled } = useMission();
  const globeRef = useRef<THREE.Group>(null);
  const { gl } = useThree();

  const [moonTexture, setMoonTexture] = useState<THREE.Texture | null>(null);
  const [topoTexture, setTopoTexture] = useState<THREE.Texture | null>(null);
  const [normalTexture, setNormalTexture] = useState<THREE.Texture | null>(null);
  const [bumpTexture, setBumpTexture] = useState<THREE.Texture | null>(null);

  const radius = 5; // Sahne küre yarıçapı

  // Dikişsiz 2048x1024 NASA Moon Trek Dokusunu Yükleme
  useEffect(() => {
    const loader = new THREE.TextureLoader();
    const maxAnisotropy = gl.capabilities.getMaxAnisotropy() || 16;

    // 1. Moon Trek LRO WAC Global Mozaik (Dikişsiz tam oturan harita)
    loader.load(
      assetUrl('textures/moon_trek_wac_4k.jpg'),
      (texture) => {
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = maxAnisotropy;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = true;
        texture.needsUpdate = true;
        setMoonTexture(texture);
      }
    );

    // 1b. QuickMap LOLA Renkli Topoğrafya Haritası (Colorized Elevation)
    loader.load(
      assetUrl('textures/moon_quickmap_topo_4k.jpg'),
      (texture) => {
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = maxAnisotropy;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = true;
        texture.needsUpdate = true;
        setTopoTexture(texture);
      }
    );

    // 2. Yüksek Çözünürlüklü Normal Haritası
    loader.load(
      assetUrl('textures/moon_normal_4k.jpg'),
      (texture) => {
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.anisotropy = maxAnisotropy;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = true;
        texture.needsUpdate = true;
        setNormalTexture(texture);
      }
    );

    // 3. LOLA Bump Haritası
    loader.load(
      assetUrl('textures/moon_lola_bump_1k.jpg'),
      (texture) => {
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.anisotropy = maxAnisotropy;
        setBumpTexture(texture);
      }
    );
  }, [gl]);

  // Site01 ve Site04 yüzey konumları (radius tam 5.0)
  const site01Vec = useMemo(() => latLonToVector3(SITES.Site01.lat, SITES.Site01.lonEast, radius), [radius]);
  const site04Vec = useMemo(() => latLonToVector3(SITES.Site04.lat, SITES.Site04.lonEast, radius), [radius]);

  // Yüzey normalleri (küre merkezinden yüzeye doğru birim vektör)
  const site01Normal = useMemo(() => site01Vec.clone().normalize(), [site01Vec]);
  const site04Normal = useMemo(() => site04Vec.clone().normalize(), [site04Vec]);

  // Pin başlığı pozisyonları (yüzeyden 0.25 birim yukarıda)
  const site01PinHead = useMemo(() => site01Vec.clone().add(site01Normal.clone().multiplyScalar(0.25)), [site01Vec, site01Normal]);
  const site04PinHead = useMemo(() => site04Vec.clone().add(site04Normal.clone().multiplyScalar(0.25)), [site04Vec, site04Normal]);

  // Hafif otomatik dönüş
  useFrame((_, delta) => {
    if (globeRef.current) {
      globeRef.current.rotation.y += delta * 0.012;
    }
  });

  return (
    <group ref={globeRef}>
      {/* 3B Ay Küresi: Tam Oturan Dikişsiz NASA Moon Trek PBR Materyali */}
      <mesh receiveShadow castShadow>
        <sphereGeometry args={[radius, 256, 256]} />
        <meshStandardMaterial
          map={layerMode === 'wac' ? moonTexture : (topoTexture || moonTexture)}
          normalMap={normalTexture || undefined}
          normalScale={new THREE.Vector2(0.9, 0.9)}
          bumpMap={bumpTexture || undefined}
          bumpScale={0.035}
          displacementMap={displacementEnabled ? (bumpTexture || undefined) : undefined}
          displacementScale={0.06}
          roughness={0.92}
          metalness={0.04}
        />
      </mesh>

      {/* Güney Kutup Referans Çemberi (-90° Enlem) - Yatay XZ Düzleminde */}
      <mesh position={[0, -radius - 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.08, 0.18, 48]} />
        <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.7} />
      </mesh>

      {/* Site01 (Connecting Ridge) Yüzeye Kilitli Pin */}
      <group>
        {/* Yüzeyden dik çıkan pin iğnesi */}
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([site01Vec, site01PinHead]);
            }}
          />
          <lineBasicMaterial color={siteId === 'Site01' ? '#38bdf8' : '#94a3b8'} linewidth={2} />
        </line>

        {/* Pin Tepe Küresi */}
        <mesh
          position={site01PinHead}
          onClick={(e) => {
            e.stopPropagation();
            setSiteId('Site01');
            setCameraMode('terrain');
          }}
          onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
          onPointerOut={() => { document.body.style.cursor = 'default'; }}
        >
          <sphereGeometry args={[0.09, 20, 20]} />
          <meshStandardMaterial
            color={siteId === 'Site01' ? '#38bdf8' : '#cbd5e1'}
            emissive={siteId === 'Site01' ? '#0284c7' : '#334155'}
            emissiveIntensity={1.2}
            roughness={0.2}
          />
        </mesh>

        {/* Etiket - Kompakt, Occluded, Düşük Z-Index, Çakışmayan */}
        <Html
          position={site01PinHead.clone().add(site01Normal.clone().multiplyScalar(0.18))}
          center
          distanceFactor={9}
          occlude
          zIndexRange={[1, 0]}
        >
          <div
            onClick={(e) => {
              e.stopPropagation();
              setSiteId('Site01');
              setCameraMode('terrain');
            }}
            className={`px-2 py-0.5 rounded-full text-[9px] font-mono whitespace-nowrap cursor-pointer transition-all border shadow-md flex items-center gap-1 ${
              siteId === 'Site01'
                ? 'bg-sky-950/95 text-sky-300 border-sky-400 font-bold shadow-sky-900/60 ring-1 ring-sky-400/50'
                : 'bg-space-950/85 text-slate-300 border-slate-700/80 hover:border-sky-500/60 hover:text-white'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${siteId === 'Site01' ? 'bg-sky-400 animate-pulse' : 'bg-slate-400'}`} />
            <span>Site01: Connecting Ridge</span>
          </div>
        </Html>
      </group>

      {/* Site04 (Shackleton Rim) Yüzeye Kilitli Pin */}
      <group>
        {/* Pin İğnesi */}
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([site04Vec, site04PinHead]);
            }}
          />
          <lineBasicMaterial color={siteId === 'Site04' ? '#38bdf8' : '#94a3b8'} linewidth={2} />
        </line>

        {/* Pin Tepe Küresi */}
        <mesh
          position={site04PinHead}
          onClick={(e) => {
            e.stopPropagation();
            setSiteId('Site04');
            setCameraMode('terrain');
          }}
          onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
          onPointerOut={() => { document.body.style.cursor = 'default'; }}
        >
          <sphereGeometry args={[0.09, 20, 20]} />
          <meshStandardMaterial
            color={siteId === 'Site04' ? '#38bdf8' : '#cbd5e1'}
            emissive={siteId === 'Site04' ? '#0284c7' : '#334155'}
            emissiveIntensity={1.2}
            roughness={0.2}
          />
        </mesh>

        {/* Etiket - Kompakt, Occluded, Düşük Z-Index, Çakışmayan */}
        <Html
          position={site04PinHead.clone().add(site04Normal.clone().multiplyScalar(0.18))}
          center
          distanceFactor={9}
          occlude
          zIndexRange={[1, 0]}
        >
          <div
            onClick={(e) => {
              e.stopPropagation();
              setSiteId('Site04');
            }}
            className={`px-2 py-0.5 rounded-full text-[9px] font-mono whitespace-nowrap cursor-pointer transition-all border shadow-md flex items-center gap-1 ${
              siteId === 'Site04'
                ? 'bg-sky-950/95 text-sky-300 border-sky-400 font-bold shadow-sky-900/60 ring-1 ring-sky-400/50'
                : 'bg-space-950/85 text-slate-300 border-slate-700/80 hover:border-sky-500/60 hover:text-white'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${siteId === 'Site04' ? 'bg-sky-400 animate-pulse' : 'bg-slate-400'}`} />
            <span>Site04: Shackleton Rim</span>
          </div>
        </Html>
      </group>
    </group>
  );
};
