import { assetUrl } from '../../services/assetUrl';
import React, { useRef, useMemo, useState, useEffect } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { useMission } from '../../context/MissionContext';
import { SITES } from '../../services/dataService';
import { CRATER_CATALOG } from '../../services/craterCatalog';
import { SiteId, CraterFeature } from '../../types';

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

/**
 * NASA Moon Trek Geometrik Ufuk Testli Görev Pini (Site01 & Site04).
 * Raycast yapmadan, doğrudan küresel yüzey normali ile kamera yön vektörünün iç çarpımı (dot product) hesaplanır.
 */
const SiteMarker: React.FC<{
  siteKey: 'Site01' | 'Site04';
  title: string;
  badge: string;
  badgeBg: string;
  vec: THREE.Vector3;
  pinHead: THREE.Vector3;
  normal: THREE.Vector3;
  isSelected: boolean;
  pinGeometry: THREE.BufferGeometry;
  activeMaterial: THREE.Material;
  inactiveMaterial: THREE.Material;
  onSelect: (site: SiteId) => void;
}> = React.memo(({
  siteKey,
  title,
  badge,
  badgeBg,
  vec,
  pinHead,
  normal,
  isSelected,
  pinGeometry,
  activeMaterial,
  inactiveMaterial,
  onSelect
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const htmlRef = useRef<HTMLDivElement>(null);

  useFrame(({ camera }) => {
    const camX = camera.position.x - pinHead.x;
    const camY = camera.position.y - pinHead.y;
    const camZ = camera.position.z - pinHead.z;
    const lenSq = camX * camX + camY * camY + camZ * camZ;
    if (lenSq < 0.0001) return;
    const invLen = 1 / Math.sqrt(lenSq);
    const dot = (normal.x * camX + normal.y * camY + normal.z * camZ) * invLen;

    const isFacing = dot > 0.05;
    if (groupRef.current && groupRef.current.visible !== isFacing) {
      groupRef.current.visible = isFacing;
    }
    if (htmlRef.current) {
      const targetDisplay = isFacing ? 'flex' : 'none';
      if (htmlRef.current.style.display !== targetDisplay) {
        htmlRef.current.style.display = targetDisplay;
      }
    }
  });

  return (
    <group ref={groupRef}>
      <line>
        <bufferGeometry
          attach="geometry"
          onUpdate={(self) => {
            self.setFromPoints([vec, pinHead]);
          }}
        />
        <lineBasicMaterial color={isSelected ? '#38bdf8' : '#64748b'} linewidth={2} />
      </line>

      <mesh
        position={pinHead}
        geometry={pinGeometry}
        material={isSelected ? activeMaterial : inactiveMaterial}
        scale={0.085}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(siteKey);
        }}
        onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { document.body.style.cursor = 'default'; }}
      />

      <Html
        position={pinHead.clone().add(normal.clone().multiplyScalar(0.16))}
        center
        distanceFactor={9}
        zIndexRange={[10, 0]}
      >
        <div
          ref={htmlRef}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(siteKey);
          }}
          className={`px-2 py-0.5 rounded-full text-[9px] font-mono whitespace-nowrap cursor-pointer transition-all border shadow-lg flex items-center gap-1.5 ${
            isSelected
              ? 'bg-sky-950/95 text-sky-200 border-sky-400 font-bold shadow-sky-900/60 ring-1 ring-sky-400/50'
              : 'bg-space-950/90 text-slate-300 border-slate-700/80 hover:border-sky-500/60'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-sky-400 animate-pulse' : 'bg-slate-400'}`} />
          <span>{title}</span>
          <span className={`text-[7.5px] px-1 py-0.2 rounded font-bold ${badgeBg}`}>{badge}</span>
        </div>
      </Html>
    </group>
  );
});

/**
 * NASA Moon Trek Kademeli LOD Krater/Özellik İşaretçisi.
 * Raycast yapmadan, doğrudan küresel yüzey normali ile kamera yön vektörünün iç çarpımı (dot product) hesaplanır.
 * Bu yöntem CPU üzerinde 480 milyon raycast testini sıfırlar ve 60 FPS akıcılık sağlar.
 */
const FeatureMarker: React.FC<{
  feature: CraterFeature;
  posHead: THREE.Vector3;
  normal: THREE.Vector3;
  isSelected: boolean;
  featureTier: number;
  currentZoomTier: 1 | 2 | 3;
  labelDisplayMode: 'lod' | 'all' | 'off';
  color: string;
  badgeBg: string;
  badgeBorder: string;
  typeBadge: string;
  pinGeometry: THREE.BufferGeometry;
  pinMaterial: THREE.Material;
  onSelect: (feature: CraterFeature) => void;
}> = React.memo(({
  feature,
  posHead,
  normal,
  isSelected,
  featureTier,
  currentZoomTier,
  labelDisplayMode,
  color,
  badgeBg,
  badgeBorder,
  typeBadge,
  pinGeometry,
  pinMaterial,
  onSelect
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const htmlRef = useRef<HTMLDivElement>(null);

  // Kademeli LOD Görünürlüğü
  const isVisibleByZoom =
    labelDisplayMode === 'all' ||
    isSelected ||
    (labelDisplayMode === 'lod' && featureTier <= currentZoomTier);

  const shouldRenderLabel = isVisibleByZoom && labelDisplayMode !== 'off';

  useFrame(({ camera }) => {
    const camX = camera.position.x - posHead.x;
    const camY = camera.position.y - posHead.y;
    const camZ = camera.position.z - posHead.z;
    const lenSq = camX * camX + camY * camY + camZ * camZ;
    if (lenSq < 0.0001) return;
    const invLen = 1 / Math.sqrt(lenSq);
    const dot = (normal.x * camX + normal.y * camY + normal.z * camZ) * invLen;

    const isFacing = dot > 0.06;

    if (groupRef.current && groupRef.current.visible !== isFacing) {
      groupRef.current.visible = isFacing;
    }

    if (htmlRef.current) {
      const show = isFacing && shouldRenderLabel;
      const targetDisplay = show ? 'flex' : 'none';
      if (htmlRef.current.style.display !== targetDisplay) {
        htmlRef.current.style.display = targetDisplay;
      }
    }
  });

  const scale = isSelected ? 0.055 : (featureTier === 1 ? 0.042 : 0.032);

  return (
    <group ref={groupRef} position={posHead}>
      {/* Hafif Paylaşımlı Küresel İşaretçi */}
      <mesh
        geometry={pinGeometry}
        material={pinMaterial}
        scale={scale}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(feature);
        }}
        onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { document.body.style.cursor = 'default'; }}
      />

      {/* Geometrik Ufuk Testi ile Raycastsiz Yüksek Performanslı Etiket */}
      <Html
        position={normal.clone().multiplyScalar(0.12)}
        center
        distanceFactor={8.5}
        zIndexRange={[5, 0]}
      >
        <div
          ref={htmlRef}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(feature);
          }}
          style={{ display: shouldRenderLabel ? 'flex' : 'none' }}
          className={`px-2 py-0.5 rounded-full text-[9px] font-mono whitespace-nowrap cursor-pointer transition-all border shadow-md items-center gap-1.5 ${badgeBg} ${badgeBorder}`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${isSelected ? 'animate-ping' : ''}`}
            style={{ backgroundColor: color }}
          />
          <span className="font-semibold">{feature.name}</span>
          {feature.diameterKm && (
            <span className="text-[8px] text-slate-400 font-sans">
              {feature.diameterKm} km
            </span>
          )}
          <span className="text-[7.5px] px-1 py-0.2 rounded bg-slate-900/80 font-bold opacity-80 uppercase">
            {typeBadge}
          </span>
        </div>
      </Html>
    </group>
  );
});

export const LunarGlobe: React.FC = () => {
  const {
    siteId,
    setSiteId,
    setCameraMode,
    layerMode,
    displacementEnabled,
    selectedCrater,
    setSelectedCrater,
    labelDisplayMode,
    featureFilterType,
    selectedSector,
    setCameraPreset
  } = useMission();
  const globeRef = useRef<THREE.Group>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial>(null);
  const { gl } = useThree();

  const [moonTexture, setMoonTexture] = useState<THREE.Texture | null>(null);
  const [topoTexture, setTopoTexture] = useState<THREE.Texture | null>(null);
  const [normalTexture, setNormalTexture] = useState<THREE.Texture | null>(null);
  const [bumpTexture, setBumpTexture] = useState<THREE.Texture | null>(null);
  const [currentZoomTier, setCurrentZoomTier] = useState<1 | 2 | 3>(1);

  const radius = 5; // Sahne küre yarıçapı

  // Tüm Güney Kutbu krater ve düzlük konumları (radius = 5.0)
  const featurePositions = useMemo(() => {
    return CRATER_CATALOG.map((feature) => {
      const vec = latLonToVector3(feature.lat, feature.lonEast, radius);
      const normal = vec.clone().normalize();
      const posHead = vec.clone().add(normal.clone().multiplyScalar(0.08));
      return { feature, vec, posHead, normal };
    });
  }, [radius]);

  // Paylaşımlı Geometri ve Materyal Havuzları (GPU Buffer ve Bellek Optimizasyonu)
  const pinGeometry = useMemo(() => new THREE.SphereGeometry(1, 10, 10), []);

  const materials = useMemo(() => ({
    crater: new THREE.MeshStandardMaterial({ color: '#f59e0b', emissive: '#f59e0b', emissiveIntensity: 0.7, roughness: 0.25 }),
    craterSelected: new THREE.MeshStandardMaterial({ color: '#f59e0b', emissive: '#f59e0b', emissiveIntensity: 1.6, roughness: 0.1 }),
    plain: new THREE.MeshStandardMaterial({ color: '#22c55e', emissive: '#22c55e', emissiveIntensity: 0.7, roughness: 0.25 }),
    plainSelected: new THREE.MeshStandardMaterial({ color: '#22c55e', emissive: '#22c55e', emissiveIntensity: 1.6, roughness: 0.1 }),
    peak: new THREE.MeshStandardMaterial({ color: '#38bdf8', emissive: '#38bdf8', emissiveIntensity: 0.7, roughness: 0.25 }),
    peakSelected: new THREE.MeshStandardMaterial({ color: '#38bdf8', emissive: '#38bdf8', emissiveIntensity: 1.6, roughness: 0.1 }),
    site: new THREE.MeshStandardMaterial({ color: '#c084fc', emissive: '#c084fc', emissiveIntensity: 0.7, roughness: 0.25 }),
    siteSelected: new THREE.MeshStandardMaterial({ color: '#c084fc', emissive: '#c084fc', emissiveIntensity: 1.6, roughness: 0.1 }),
    missionActive: new THREE.MeshStandardMaterial({ color: '#38bdf8', emissive: '#0284c7', emissiveIntensity: 1.4, roughness: 0.2 }),
    missionInactive: new THREE.MeshStandardMaterial({ color: '#94a3b8', emissive: '#1e293b', emissiveIntensity: 0.5, roughness: 0.4 }),
  }), []);

  // NASA Moon Trek ve QuickMap dokularını aşamalı (Progressive) yükleme:
  // İlk önce ultra hafif 1K dokular anında yüklenir (boş/karanlık küre beklemesini engeller),
  // ardından 4K yüksek çözünürlüklü PBR haritaları arka planda kesintisiz devreye girer.
  useEffect(() => {
    const loader = new THREE.TextureLoader();
    // Anizotropi 8x olarak ayarlandı (Kutup ve ufuk açılarında kristal netlik sağlar)
    const maxAnisotropy = Math.min(gl.capabilities.getMaxAnisotropy() || 8, 8);

    const configureTexture = (tex: THREE.Texture, isColor: boolean = true) => {
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.ClampToEdgeWrapping;
      if (isColor) {
        tex.colorSpace = THREE.SRGBColorSpace;
      }
      tex.anisotropy = maxAnisotropy;
      tex.minFilter = THREE.LinearMipmapLinearFilter;
      tex.magFilter = THREE.LinearFilter;
      tex.generateMipmaps = true;
      tex.needsUpdate = true;
      return tex;
    };

    let wac4kLoaded = false;
    let topo4kLoaded = false;
    let normal4kLoaded = false;
    let bump4kLoaded = false;

    // 1. Aşama: Anlık 1K Hızlı Yükleme (İlk açılışta gecikmesiz Ay kaplaması)
    loader.load(assetUrl('textures/moon_trek_wac_1k.jpg'), (tex) => {
      if (!wac4kLoaded) setMoonTexture(configureTexture(tex, true));
    });
    loader.load(assetUrl('textures/moon_quickmap_topo_1k.jpg'), (tex) => {
      if (!topo4kLoaded) setTopoTexture(configureTexture(tex, true));
    });
    loader.load(assetUrl('textures/moon_normal_1k.jpg'), (tex) => {
      if (!normal4kLoaded) setNormalTexture(configureTexture(tex, false));
    });
    loader.load(assetUrl('textures/moon_lola_bump_1k.jpg'), (tex) => {
      if (!bump4kLoaded) setBumpTexture(configureTexture(tex, false));
    });

    // 2. Aşama: 4K Master Yüksek Çözünürlüklü Detay Yükleme
    loader.load(assetUrl('textures/moon_trek_wac_4k.jpg'), (tex) => {
      wac4kLoaded = true;
      setMoonTexture(configureTexture(tex, true));
    });
    loader.load(assetUrl('textures/moon_quickmap_topo_4k.jpg'), (tex) => {
      topo4kLoaded = true;
      setTopoTexture(configureTexture(tex, true));
    });
    loader.load(assetUrl('textures/moon_normal_4k_smooth.jpg'), (tex) => {
      normal4kLoaded = true;
      setNormalTexture(configureTexture(tex, false));
    });
    loader.load(assetUrl('textures/moon_lola_bump_4k.jpg'), (tex) => {
      bump4kLoaded = true;
      setBumpTexture(configureTexture(tex, false));
    });
  }, [gl]);

  // Doku ve katman değişimlerinde Three.js shader programının anında güncellenmesini garanti et
  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.needsUpdate = true;
    }
  }, [moonTexture, topoTexture, normalTexture, bumpTexture, layerMode, displacementEnabled]);

  // Site01 ve Site04 yüzey konumları
  const site01Vec = useMemo(() => latLonToVector3(SITES.Site01.lat, SITES.Site01.lonEast, radius), [radius]);
  const site04Vec = useMemo(() => latLonToVector3(SITES.Site04.lat, SITES.Site04.lonEast, radius), [radius]);
  const site01Normal = useMemo(() => site01Vec.clone().normalize(), [site01Vec]);
  const site04Normal = useMemo(() => site04Vec.clone().normalize(), [site04Vec]);
  const site01PinHead = useMemo(() => site01Vec.clone().add(site01Normal.clone().multiplyScalar(0.22)), [site01Vec, site01Normal]);
  const site04PinHead = useMemo(() => site04Vec.clone().add(site04Normal.clone().multiplyScalar(0.22)), [site04Vec, site04Normal]);

  // Kamera mesafesine göre kademeli yakınlaşma (LOD - Level of Detail) hesaplaması
  // Ay'ın Güney Kutbu (0, -radius, 0) yüzeyine olan gerçek mesafe baz alınır
  const southPolePos = useMemo(() => new THREE.Vector3(0, -radius, 0), [radius]);

  useFrame(({ camera }) => {
    const distToPole = camera.position.distanceTo(southPolePos);
    let calculatedTier: 1 | 2 | 3 = currentZoomTier;
    // Histerezis (Deadband) ile sınır bölgelerindeki gereksiz React renderlarını engelle
    if (currentZoomTier === 1 && distToPole < 8.8) {
      calculatedTier = 2;
    } else if (currentZoomTier === 2) {
      if (distToPole > 9.6) calculatedTier = 1;
      else if (distToPole < 5.2) calculatedTier = 3;
    } else if (currentZoomTier === 3) {
      if (distToPole > 5.8) calculatedTier = 2;
    }

    if (calculatedTier !== currentZoomTier) {
      setCurrentZoomTier(calculatedTier);
    }
  });

  // Poligon Optimizasyonu: Standart görünümde 96x96 (18,432 üçgen, %91 poligon tasarrufu),
  // sadece vertex displacement aktifken 160x160 segment kullanılır.
  const sphereSegments = displacementEnabled ? 160 : 96;

  return (
    <group ref={globeRef}>
      {/* 3B Ay Küresi: Tam Oturan Dikişsiz NASA Moon Trek PBR Materyali */}
      <mesh>
        <sphereGeometry args={[radius, sphereSegments, sphereSegments]} />
        <meshStandardMaterial
          ref={materialRef}
          map={layerMode === 'wac' ? (moonTexture || undefined) : (topoTexture || moonTexture || undefined)}
          normalMap={displacementEnabled ? (normalTexture || undefined) : undefined}
          normalScale={new THREE.Vector2(0.35, 0.35)}
          bumpMap={displacementEnabled ? (bumpTexture || undefined) : undefined}
          bumpScale={displacementEnabled ? 0.005 : 0}
          displacementMap={displacementEnabled ? (bumpTexture || undefined) : undefined}
          displacementScale={displacementEnabled ? 0.03 : 0}
          displacementBias={0}
          roughness={0.96}
          metalness={0.0}
        />
      </mesh>

      {/* Güney Kutup Referans Çemberi (-90° Enlem) - Yatay XZ Düzleminde */}
      <mesh position={[0, -radius - 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.06, 0.22, 64]} />
        <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.8} />
      </mesh>

      {/* 80°S Enlem Referans Çemberi (Ay'ın Güney Kutbu Sınır Çemberi) */}
      <mesh position={[0, -radius * Math.sin((80 * Math.PI) / 180), 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius * Math.cos((80 * Math.PI) / 180) - 0.02, radius * Math.cos((80 * Math.PI) / 180) + 0.02, 64]} />
        <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.3} />
      </mesh>

      {/* Site01 (Connecting Ridge) Ana Görev Pini */}
      <SiteMarker
        siteKey="Site01"
        title="Site01: Connecting Ridge"
        badge="54s ORTAK"
        badgeBg="bg-sky-900/60 text-sky-300"
        vec={site01Vec}
        pinHead={site01PinHead}
        normal={site01Normal}
        isSelected={siteId === 'Site01'}
        pinGeometry={pinGeometry}
        activeMaterial={materials.missionActive}
        inactiveMaterial={materials.missionInactive}
        onSelect={setSiteId}
      />

      {/* Site04 (Shackleton Rim) Ana Görev Pini */}
      <SiteMarker
        siteKey="Site04"
        title="Site04: Shackleton Rim"
        badge="KESİNTİ"
        badgeBg="bg-red-950/60 text-red-300"
        vec={site04Vec}
        pinHead={site04PinHead}
        normal={site04Normal}
        isSelected={siteId === 'Site04'}
        pinGeometry={pinGeometry}
        activeMaterial={materials.missionActive}
        inactiveMaterial={materials.missionInactive}
        onSelect={setSiteId}
      />

      {/* Güney Kutbu Tüm Krater, Düzlük, Sırt ve Platolar (Kademeli LOD İşaretçileri) */}
      {featurePositions.map(({ feature, posHead, normal }) => {
        // Site01 ve Site04 yukarıda zaten özel pin olarak çizildi
        if (feature.id === 'feature-connecting-ridge' || feature.id === 'feature-shackleton-rim') {
          return null;
        }

        const isSelected = selectedCrater?.id === feature.id;

        // 1. Sektör filtresi
        if (selectedSector !== 'all' && feature.sector !== selectedSector) {
          return null;
        }

        // 2. Özellik türü filtresi
        if (featureFilterType === 'crater' && feature.type !== 'crater') return null;
        if (featureFilterType === 'plain' && feature.type !== 'plain' && feature.type !== 'plateau') return null;
        if (featureFilterType === 'peak' && feature.type !== 'peak' && feature.type !== 'ridge') return null;

        const featureTier = feature.tier || 1;

        // Türüne göre renk ve stil belirleme
        let color = '#f59e0b';
        let badgeBorder = 'border-amber-500/50';
        let badgeBg = 'bg-slate-950/90 text-amber-300';
        let typeBadge = 'KRATER';
        let pinMaterial = isSelected ? materials.craterSelected : materials.crater;

        if (feature.type === 'plain' || feature.type === 'plateau') {
          color = '#22c55e';
          badgeBorder = 'border-emerald-500/50';
          badgeBg = 'bg-slate-950/90 text-emerald-300';
          typeBadge = feature.type === 'plateau' ? 'PLATO' : 'DÜZLÜK';
          pinMaterial = isSelected ? materials.plainSelected : materials.plain;
        } else if (feature.type === 'peak' || feature.type === 'ridge') {
          color = '#38bdf8';
          badgeBorder = 'border-sky-500/50';
          badgeBg = 'bg-slate-950/90 text-sky-300';
          typeBadge = feature.type === 'peak' ? 'ZİRVE' : 'SIRT';
          pinMaterial = isSelected ? materials.peakSelected : materials.peak;
        } else if (feature.type === 'site') {
          color = '#c084fc';
          badgeBorder = 'border-purple-500/50';
          badgeBg = 'bg-slate-950/90 text-purple-200';
          typeBadge = 'KUTUP';
          pinMaterial = isSelected ? materials.siteSelected : materials.site;
        }

        if (isSelected) {
          badgeBorder = 'border-amber-400 ring-2 ring-amber-400/60 shadow-amber-900/60';
          badgeBg = 'bg-amber-950/95 text-amber-200 font-bold';
        }

        return (
          <FeatureMarker
            key={feature.id}
            feature={feature}
            posHead={posHead}
            normal={normal}
            isSelected={isSelected}
            featureTier={featureTier}
            currentZoomTier={currentZoomTier}
            labelDisplayMode={labelDisplayMode}
            color={color}
            badgeBg={badgeBg}
            badgeBorder={badgeBorder}
            typeBadge={typeBadge}
            pinGeometry={pinGeometry}
            pinMaterial={pinMaterial}
            onSelect={setSelectedCrater}
          />
        );
      })}
    </group>
  );
};
