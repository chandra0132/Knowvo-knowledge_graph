import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function ThreeOrbHero() {
  const mountRef = useRef(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const width = mountRef.current.clientWidth || 320;
    const height = mountRef.current.clientHeight || 320;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 32;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mountRef.current.appendChild(renderer.domElement);

    // 2. Center Orb Group
    const orbGroup = new THREE.Group();
    scene.add(orbGroup);

    // Core Glowing Sphere
    const coreGeo = new THREE.SphereGeometry(4.5, 32, 32);
    const coreMat = new THREE.MeshPhongMaterial({
      color: 0x4f46e5,
      emissive: 0x38bdf8,
      emissiveIntensity: 0.45,
      shininess: 90,
      transparent: true,
      opacity: 0.85,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    orbGroup.add(coreMesh);

    // Outer Geodesic Wireframe Lattice (Knowledge Lattice)
    const latticeGeo = new THREE.IcosahedronGeometry(7.5, 2);
    const latticeMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.45,
    });
    const latticeMesh = new THREE.Mesh(latticeGeo, latticeMat);
    orbGroup.add(latticeMesh);

    // Glowing Node Points at Vertices
    const vertexPositions = latticeGeo.attributes.position.array;
    const pointCount = vertexPositions.length / 3;
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertexPositions), 3));
    const pMat = new THREE.PointsMaterial({
      color: 0x00f0ff,
      size: 0.65,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
    });
    const pointMesh = new THREE.Points(pGeo, pMat);
    orbGroup.add(pointMesh);

    // Outer Rotating Orbital Ring 1
    const ring1Geo = new THREE.TorusGeometry(10.5, 0.12, 16, 100);
    const ring1Mat = new THREE.MeshBasicMaterial({
      color: 0xc084fc,
      transparent: true,
      opacity: 0.65,
    });
    const ring1Mesh = new THREE.Mesh(ring1Geo, ring1Mat);
    ring1Mesh.rotation.x = Math.PI / 3;
    orbGroup.add(ring1Mesh);

    // Outer Rotating Orbital Ring 2
    const ring2Geo = new THREE.TorusGeometry(12, 0.08, 16, 100);
    const ring2Mat = new THREE.MeshBasicMaterial({
      color: 0x34d399,
      transparent: true,
      opacity: 0.5,
    });
    const ring2Mesh = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2Mesh.rotation.y = Math.PI / 4;
    ring2Mesh.rotation.x = -Math.PI / 4;
    orbGroup.add(ring2Mesh);

    // 3. Dynamic Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x00f0ff, 2.5, 50);
    pointLight1.position.set(15, 15, 15);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0xa855f7, 2.0, 50);
    pointLight2.position.set(-15, -15, 10);
    scene.add(pointLight2);

    // 4. Mouse Rotation Interaction
    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    const handleMouseMove = (e) => {
      const rect = mountRef.current?.getBoundingClientRect();
      if (!rect) return;
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      mouseX = (clientX / rect.width - 0.5) * 2;
      mouseY = (clientY / rect.height - 0.5) * 2;
    };

    const domElement = mountRef.current;
    domElement.addEventListener('mousemove', handleMouseMove);

    // 5. Animation Loop
    let clock = new THREE.Clock();
    let animId;

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth mouse follow
      targetX += (mouseX * 0.8 - targetX) * 0.08;
      targetY += (mouseY * 0.8 - targetY) * 0.08;

      orbGroup.rotation.y = elapsed * 0.25 + targetX;
      orbGroup.rotation.x = elapsed * 0.15 + targetY;

      // Pulse core
      const scale = 1 + Math.sin(elapsed * 2) * 0.05;
      coreMesh.scale.set(scale, scale, scale);

      // Rotate rings on unique axes
      ring1Mesh.rotation.z = elapsed * 0.4;
      ring2Mesh.rotation.z = elapsed * -0.3;

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      domElement.removeEventListener('mousemove', handleMouseMove);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{
        width: '100%',
        height: '320px',
        position: 'relative',
        cursor: 'grab',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    />
  );
}
