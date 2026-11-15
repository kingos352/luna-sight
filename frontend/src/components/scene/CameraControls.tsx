import React, { useEffect, useRef } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { useMission } from '../../context/MissionContext';

export const CameraControls: React.FC = () => {
  const { cameraMode, terrainData, cameraPreset, setCameraPreset } = useMission();
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();

  // Handle camera presets
  useEffect(() => {
    if (!controlsRef.current || !cameraPreset) return;

    if (cameraPreset === 'south_pole') {
      camera.position.set(0, -11.8, 1.5);
      camera.lookAt(0, -4.8, 0);
      controlsRef.current.target.set(0, -4.8, 0);
    } else if (cameraPreset === 'site01') {
      camera.position.set(-1.2, -8.8, 2.2);
      camera.lookAt(0, -4.8, 0);
      controlsRef.current.target.set(0, -4.8, 0);
    } else if (cameraPreset === 'site04') {
      camera.position.set(0.8, -9.2, 2.4);
      camera.lookAt(0, -4.8, 0);
      controlsRef.current.target.set(0, -4.8, 0);
    } else if (cameraPreset === 'shoemaker') {
      camera.position.set(2.4, -8.5, 2.2);
      camera.lookAt(0.5, -4.8, 0.5);
      controlsRef.current.target.set(0.5, -4.8, 0.5);
    } else if (cameraPreset === 'malapert') {
      camera.position.set(-2.5, -8.2, -1.8);
      camera.lookAt(-0.6, -4.8, -0.4);
      controlsRef.current.target.set(-0.6, -4.8, -0.4);
    } else if (cameraPreset === 'amundsen') {
      camera.position.set(3.0, -8.0, 1.2);
      camera.lookAt(0.8, -4.8, 0.4);
      controlsRef.current.target.set(0.8, -4.8, 0.4);
    } else if (cameraPreset === 'equatorial') {
      camera.position.set(0, 2.5, 12);
      camera.lookAt(0, 0, 0);
      controlsRef.current.target.set(0, 0, 0);
    }
    controlsRef.current.update();
    setCameraPreset(null);
  }, [cameraPreset, camera, setCameraPreset]);

  useEffect(() => {
    if (!controlsRef.current) return;

    if (cameraMode === 'globe') {
      // Güney kutbunu doğrudan görecek açı
      camera.position.set(0, -9, 8);
      camera.lookAt(0, 0, 0);
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.minDistance = 6;
      controlsRef.current.maxDistance = 25;
      controlsRef.current.enablePan = true;
    } else if (cameraMode === 'terrain') {
      // Serbest 8 km gerçek LOLA panoramik arazi perspektifi
      camera.position.set(1600, 2000, 2800);
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.minDistance = 5;
      controlsRef.current.maxDistance = 15000;
      controlsRef.current.enablePan = true;
    } else if (cameraMode === 'surface_pov') {
      // Gözlemci POV: (0, 2.0, 0) noktasından Dünya yönüne bakış (Az: 130.73°, Alt: +1.07°)
      // Dünya vektör yönü: Az 130.73°, Alt 1.07°
      const azRad = (130.730898 * Math.PI) / 180;
      const altRad = (1.074733 * Math.PI) / 180;
      const dist = 50;
      const dx = dist * Math.cos(altRad) * Math.sin(azRad);
      const dy = dist * Math.sin(altRad);
      const dz = -dist * Math.cos(altRad) * Math.cos(azRad);

      camera.position.set(-dx * 0.1, 2.5, -dz * 0.1);
      controlsRef.current.target.set(dx, 2.0 + dy, dz);
      controlsRef.current.minDistance = 1;
      controlsRef.current.maxDistance = 150;
    }

    controlsRef.current.update();
  }, [cameraMode, camera]);

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.08}
      rotateSpeed={0.8}
    />
  );
};
