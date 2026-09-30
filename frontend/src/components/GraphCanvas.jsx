import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { ZoomIn, ZoomOut, RefreshCw, Maximize2, Sparkles, Filter, X, Box, Compass } from 'lucide-react';

const ENTITY_COLORS = {
  Model: '#00f0ff',       // Neon Sky
  Method: '#6366f1',      // Indigo
  Dataset: '#10b981',     // Emerald
  Metric: '#f59e0b',      // Amber
  Problem: '#f43f5e',     // Rose
  Architecture: '#a855f7',// Purple
  Task: '#ec4899',        // Pink
  Concept: '#818cf8',     // Soft Violet
  Entity: '#06b6d4',      // Cyan Default
};

export default function GraphCanvas({ graphData, onNodeSelect }) {
  const containerRef = useRef(null);
  const canvas3DRef = useRef(null);
  const canvas2DRef = useRef(null);
  const animFrameRef = useRef(null);

  // Mode: '3D' or '2D'
  const [viewMode, setViewMode] = useState('3D');
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [filterType, setFilterType] = useState('ALL');
  const [autoRotate, setAutoRotate] = useState(true);

  // 3D Scene Refs
  const threeRef = useRef({
    scene: null,
    camera: null,
    renderer: null,
    nodeMeshes: [],
    linkLines: [],
    photonParticles: null,
    isDragging: false,
    prevMouse: { x: 0, y: 0 },
    spherical: { radius: 110, theta: 0.5, phi: 1.2 },
    target: new THREE.Vector3(0, 0, 0),
    raycaster: new THREE.Raycaster(),
    mouseVec: new THREE.Vector2(),
  });

  // 2D State
  const [transform2D, setTransform2D] = useState({ k: 1, x: 0, y: 0 });
  const nodes2DRef = useRef([]);
  const links2DRef = useRef([]);

  // ==========================================
  // 1. THREE.JS 3D/2D WEBGL GRAPH INITIALIZATION
  // ==========================================
  useEffect(() => {
    if (!canvas3DRef.current) return;

    const width = canvas3DRef.current.clientWidth || 700;
    const height = canvas3DRef.current.clientHeight || 500;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, Math.max(0.1, width / (height || 1)), 0.1, 2000);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    canvas3DRef.current.innerHTML = '';
    canvas3DRef.current.appendChild(renderer.domElement);

    // Set camera position based on mode
    if (viewMode === '2D') {
      threeRef.current.spherical.phi = Math.PI / 2;
      threeRef.current.spherical.theta = 0;
      threeRef.current.spherical.radius = 90;
    } else {
      threeRef.current.spherical.phi = Math.PI / 3;
      threeRef.current.spherical.theta = 0.5;
      threeRef.current.spherical.radius = 85;
    }

    // Ambient and Point Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.95);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(50, 100, 80);
    scene.add(dirLight);

    const pointLight = new THREE.PointLight(0x00f0ff, 2, 200);
    pointLight.position.set(0, 0, 0);
    scene.add(pointLight);

    threeRef.current.scene = scene;
    threeRef.current.camera = camera;
    threeRef.current.renderer = renderer;

    // Build Nodes and Links from graphData
    build3DGraph(graphData, scene, viewMode);

    // Resize listener with ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        if (w > 0 && h > 0 && renderer && camera) {
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          renderer.setSize(w, h);
        }
      }
    });

    if (canvas3DRef.current) {
      resizeObserver.observe(canvas3DRef.current);
    }

    const handleResize = () => {
      if (!canvas3DRef.current || !renderer) return;
      const w = canvas3DRef.current.clientWidth;
      const h = canvas3DRef.current.clientHeight;
      if (w > 0 && h > 0) {
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      }
    };

    window.addEventListener('resize', handleResize);

    // Animation Loop
    let clock = new THREE.Clock();
    let animId;

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Auto Orbit Rotation if enabled (only in 3D mode)
      if (autoRotate && viewMode === '3D' && !threeRef.current.isDragging) {
        threeRef.current.spherical.theta += 0.003;
      }

      // Update Camera from spherical coords
      const sph = threeRef.current.spherical;
      camera.position.x = sph.radius * Math.sin(sph.phi) * Math.sin(sph.theta);
      camera.position.y = sph.radius * Math.cos(sph.phi);
      camera.position.z = sph.radius * Math.sin(sph.phi) * Math.cos(sph.theta);
      camera.lookAt(threeRef.current.target);

      // Animate Nodes (gentle float pulse)
      threeRef.current.nodeMeshes.forEach((mesh, idx) => {
        if (viewMode === '3D') {
          mesh.rotation.y = elapsed * 0.5 + idx;
        }
        const scale = 1 + Math.sin(elapsed * 2 + idx) * 0.04;
        mesh.scale.set(scale, scale, scale);
      });

      // Animate Photon Particles along link paths
      const photons = threeRef.current.photonParticles;
      if (photons && photons.geometry.attributes.position) {
        const posAttr = photons.geometry.attributes.position;
        const positions = posAttr.array;
        const speed = 0.015;

        for (let i = 0; i < positions.length / 3; i++) {
          const lData = photons.userData.linksData[i];
          if (lData) {
            lData.progress = (lData.progress + speed) % 1;
            const p = lData.progress;
            positions[i * 3] = lData.src.x + (lData.dst.x - lData.src.x) * p;
            positions[i * 3 + 1] = lData.src.y + (lData.dst.y - lData.src.y) * p;
            positions[i * 3 + 2] = lData.src.z + (lData.dst.z - lData.src.z) * p;
          }
        }
        posAttr.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
    };
  }, [viewMode, graphData, autoRotate]);

  // Build 3D Graph Meshes
  const build3DGraph = (data, scene, mode = '3D') => {
    if (!data || !data.nodes || data.nodes.length === 0) return;

    // Clean previous
    threeRef.current.nodeMeshes.forEach((m) => scene.remove(m));
    threeRef.current.linkLines.forEach((l) => scene.remove(l));
    if (threeRef.current.photonParticles) scene.remove(threeRef.current.photonParticles);

    const nodes = data.nodes;
    const links = data.links || [];
    const count = nodes.length;

    const node3DMap = new Map();
    const nodeMeshes = [];

    // Position Nodes in 3D Spherical or 2D Planar Space
    const phi = Math.PI * (3 - Math.sqrt(5)); // Golden angle

    nodes.forEach((n, i) => {
      let x = 0, posY = 0, z = 0;

      if (mode === '2D') {
        const radius = Math.min(50, 18 + Math.sqrt(i + 1) * 8.5);
        const angle = i * 0.8;
        x = Math.cos(angle) * radius;
        posY = Math.sin(angle) * radius;
        z = 0;
      } else {
        const y = 1 - (i / Math.max(1, count - 1)) * 2; // y goes from 1 to -1
        const radiusAtY = Math.sqrt(Math.max(0, 1 - y * y));
        const theta = phi * i;

        const sphereRadius = Math.min(65, 30 + Math.sqrt(count) * 6);
        x = Math.cos(theta) * radiusAtY * sphereRadius;
        z = Math.sin(theta) * radiusAtY * sphereRadius;
        posY = y * sphereRadius;
      }

      // Sphere Geometry for Node
      const colHex = ENTITY_COLORS[n.type] || ENTITY_COLORS.Entity;
      const nodeSize = n.type === 'Model' || n.type === 'Method' ? 2.6 : 2.0;

      const geo = new THREE.SphereGeometry(nodeSize, 24, 24);
      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(colHex),
        emissive: new THREE.Color(colHex),
        emissiveIntensity: 0.35,
        roughness: 0.2,
        metalness: 0.6,
      });

      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, posY, z);
      mesh.userData = { nodeData: n };

      // Outer Halo Ring
      const ringGeo = new THREE.RingGeometry(nodeSize * 1.2, nodeSize * 1.35, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(colHex),
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.5,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      mesh.add(ring);

      scene.add(mesh);
      nodeMeshes.push(mesh);
      node3DMap.set(n.id, mesh);
    });

    threeRef.current.nodeMeshes = nodeMeshes;

    // 2. Build 3D Link Lines & Photons
    const linkLines = [];
    const photonLinksData = [];

    links.forEach((l) => {
      const srcMesh = node3DMap.get(l.source);
      const dstMesh = node3DMap.get(l.target);
      if (!srcMesh || !dstMesh) return;

      // Line Geometry
      const points = [srcMesh.position, dstMesh.position];
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x6366f1,
        transparent: true,
        opacity: 0.35,
      });

      const line = new THREE.Line(lineGeo, lineMat);
      scene.add(line);
      linkLines.push(line);

      photonLinksData.push({
        src: srcMesh.position,
        dst: dstMesh.position,
        progress: Math.random(),
      });
    });

    threeRef.current.linkLines = linkLines;

    // 3. Photon Particles System
    if (photonLinksData.length > 0) {
      const pCount = photonLinksData.length;
      const pGeo = new THREE.BufferGeometry();
      const pPositions = new Float32Array(pCount * 3);

      photonLinksData.forEach((ld, idx) => {
        pPositions[idx * 3] = ld.src.x;
        pPositions[idx * 3 + 1] = ld.src.y;
        pPositions[idx * 3 + 2] = ld.src.z;
      });

      pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));

      const pMat = new THREE.PointsMaterial({
        color: 0x00f0ff,
        size: 2.2,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
      });

      const photonPoints = new THREE.Points(pGeo, pMat);
      photonPoints.userData = { linksData: photonLinksData };
      scene.add(photonPoints);
      threeRef.current.photonParticles = photonPoints;
    }
  };

  // 3D Mouse Controls (Orbit, Zoom, Raycast)
  const handle3DMouseDown = (e) => {
    threeRef.current.isDragging = true;
    threeRef.current.prevMouse = { x: e.clientX, y: e.clientY };

    // Raycast on Click
    check3DRaycast(e, (hitMesh) => {
      if (hitMesh && hitMesh.userData?.nodeData) {
        const nData = hitMesh.userData.nodeData;
        setSelectedNode(nData);
        if (onNodeSelect) onNodeSelect(nData);

        // Smooth zoom to node
        threeRef.current.target.copy(hitMesh.position);
      }
    });
  };

  const handle3DMouseMove = (e) => {
    if (threeRef.current.isDragging) {
      const dx = e.clientX - threeRef.current.prevMouse.x;
      const dy = e.clientY - threeRef.current.prevMouse.y;

      const sph = threeRef.current.spherical;
      sph.theta -= dx * 0.008;
      sph.phi = Math.max(0.1, Math.min(Math.PI - 0.1, sph.phi - dy * 0.008));

      threeRef.current.prevMouse = { x: e.clientX, y: e.clientY };
    } else {
      // Hover Raycast
      check3DRaycast(e, (hitMesh) => {
        setHoveredNode(hitMesh?.userData?.nodeData || null);
      });
    }
  };

  const handle3DMouseUp = () => {
    threeRef.current.isDragging = false;
  };

  const handle3DWheel = (e) => {
    e.preventDefault();
    const sph = threeRef.current.spherical;
    sph.radius = Math.max(30, Math.min(260, sph.radius + e.deltaY * 0.08));
  };

  const check3DRaycast = (e, callback) => {
    if (!canvas3DRef.current || !threeRef.current.camera) return;
    const rect = canvas3DRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    threeRef.current.mouseVec.set(x, y);
    threeRef.current.raycaster.setFromCamera(threeRef.current.mouseVec, threeRef.current.camera);

    const intersects = threeRef.current.raycaster.intersectObjects(threeRef.current.nodeMeshes);
    if (intersects.length > 0) {
      callback(intersects[0].object);
    } else {
      callback(null);
    }
  };

  const handleResetCamera = () => {
    threeRef.current.spherical = { radius: 110, theta: 0.5, phi: 1.2 };
    threeRef.current.target.set(0, 0, 0);
  };

  const activeNode = selectedNode || hoveredNode;

  return (
    <div
      className="brutal-panel"
      ref={containerRef}
      style={{
        padding: '1.25rem',
        height: '100%',
        minHeight: '520px',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        margin: 0,
      }}
    >
      {/* HUD Header Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.75rem',
          flexWrap: 'wrap',
          gap: '0.5rem',
          zIndex: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <Sparkles size={18} color="var(--neon-cyan)" />
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#ffffff' }}>
            3D Spatial Knowledge Universe
          </h3>
          <span className="badge-brutal cyan" style={{ fontSize: '0.7rem' }}>
            {graphData?.nodes?.length || 0} Nodes &bull; {graphData?.links?.length || 0} Links
          </span>
        </div>

        {/* Action Controls & Mode Toggle */}
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          {/* Mode Switcher */}
          <div style={{ display: 'flex', background: 'rgba(255, 255, 255, 0.08)', borderRadius: 'var(--radius-sm)', padding: '2px', border: '1px solid var(--border-glass)' }}>
            <button
              className="btn-brutal-secondary"
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.725rem',
                border: 'none',
                background: viewMode === '3D' ? 'var(--neon-cyan)' : 'transparent',
                color: viewMode === '3D' ? '#000' : 'var(--text-secondary)',
                fontWeight: 700,
              }}
              onClick={() => setViewMode('3D')}
            >
              <Box size={13} /> 3D WebGL
            </button>
            <button
              className="btn-brutal-secondary"
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.725rem',
                border: 'none',
                background: viewMode === '2D' ? 'var(--neon-cyan)' : 'transparent',
                color: viewMode === '2D' ? '#000' : 'var(--text-secondary)',
                fontWeight: 700,
              }}
              onClick={() => setViewMode('2D')}
            >
              2D Planar
            </button>
          </div>

          <button
            className="btn-brutal-secondary"
            style={{
              padding: '0.3rem 0.65rem',
              borderColor: autoRotate ? 'var(--neon-cyan)' : 'var(--border-base)',
              color: autoRotate ? 'var(--neon-cyan)' : 'var(--text-muted)',
            }}
            onClick={() => setAutoRotate(!autoRotate)}
            title="Toggle 3D Orbit Auto-Rotation"
          >
            <Compass size={14} /> {autoRotate ? 'Orbit On' : 'Orbit Off'}
          </button>

          <button className="btn-brutal-secondary" style={{ padding: '0.3rem 0.65rem' }} onClick={handleResetCamera} title="Reset 3D Camera">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Filter Chips Bar */}
      <div
        style={{
          display: 'flex',
          gap: '0.35rem',
          marginBottom: '0.65rem',
          overflowX: 'auto',
          paddingBottom: '0.2rem',
          zIndex: 20,
        }}
      >
        {['ALL', 'Model', 'Method', 'Dataset', 'Metric', 'Problem', 'Architecture'].map((t) => (
          <button
            key={t}
            onClick={() => setFilterType(t)}
            style={{
              fontSize: '0.725rem',
              fontWeight: 600,
              padding: '0.25rem 0.65rem',
              borderRadius: '999px',
              border: '1px solid',
              borderColor:
                filterType === t
                  ? t === 'ALL'
                    ? 'var(--neon-cyan)'
                    : ENTITY_COLORS[t] || 'var(--neon-cyan)'
                  : 'var(--border-subtle)',
              backgroundColor:
                filterType === t
                  ? (t === 'ALL' ? 'var(--neon-cyan)' : ENTITY_COLORS[t] || 'var(--neon-cyan)') + '25'
                  : 'rgba(255, 255, 255, 0.05)',
              color:
                filterType === t
                  ? t === 'ALL'
                    ? 'var(--neon-cyan)'
                    : ENTITY_COLORS[t] || '#fff'
                  : 'var(--text-secondary)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* 3D WebGL / 2D Canvas Viewport */}
      <div
        style={{
          flex: 1,
          minHeight: '400px',
          background: 'radial-gradient(circle at 50% 50%, #0d1224 0%, #060812 100%)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-glass)',
          position: 'relative',
          overflow: 'hidden',
          boxShadow: 'inset 0 0 30px rgba(0, 240, 255, 0.08)',
        }}
      >
        <div
          ref={canvas3DRef}
          onMouseDown={handle3DMouseDown}
          onMouseMove={handle3DMouseMove}
          onMouseUp={handle3DMouseUp}
          onWheel={handle3DWheel}
          style={{
            width: '100%',
            height: '100%',
            cursor: threeRef.current.isDragging ? 'grabbing' : 'grab',
          }}
        />

        {/* 3D Entity Inspector Card */}
        {activeNode && (
          <div
            style={{
              position: 'absolute',
              top: '14px',
              right: '14px',
              background: 'rgba(13, 18, 36, 0.92)',
              backdropFilter: 'blur(20px)',
              padding: '0.95rem 1.25rem',
              borderRadius: 'var(--radius-md)',
              border: `1.5px solid ${ENTITY_COLORS[activeNode.type] || 'var(--neon-cyan)'}`,
              fontSize: '0.8rem',
              maxWidth: '300px',
              boxShadow: '0 12px 40px rgba(0, 0, 0, 0.6), 0 0 20px rgba(0, 240, 255, 0.2)',
              zIndex: 30,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
              <div>
                <div style={{ fontWeight: 800, color: '#ffffff', fontSize: '0.95rem', letterSpacing: '-0.01em' }}>
                  {activeNode.label || activeNode.id}
                </div>
                <div
                  style={{
                    display: 'inline-block',
                    fontSize: '0.7rem',
                    color: ENTITY_COLORS[activeNode.type] || 'var(--neon-cyan)',
                    background: (ENTITY_COLORS[activeNode.type] || '#00f0ff') + '22',
                    padding: '0.15rem 0.55rem',
                    borderRadius: '999px',
                    marginTop: '0.35rem',
                    fontWeight: 700,
                  }}
                >
                  {activeNode.type || 'Entity'}
                </div>
              </div>
              {selectedNode && (
                <button
                  onClick={() => setSelectedNode(null)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  <X size={16} />
                </button>
              )}
            </div>

            <div style={{ marginTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '0.6rem' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '0.35rem' }}>
                3D SPATIAL CONNECTIONS:
              </div>
              {graphData?.links
                ?.filter((l) => l.source === activeNode.id || l.target === activeNode.id)
                .slice(0, 4)
                .map((l, idx) => (
                  <div key={idx} style={{ fontSize: '0.75rem', color: '#e2e8f0', marginBottom: '0.25rem' }}>
                    &bull; <span style={{ color: 'var(--neon-cyan)', fontWeight: 600 }}>{l.relation}</span>{' '}
                    {l.source === activeNode.id ? `&rarr; ${l.target}` : `&larr; ${l.source}`}
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 3D Legend & Orbit Hint */}
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '12px',
            background: 'rgba(13, 18, 36, 0.85)',
            backdropFilter: 'blur(12px)',
            padding: '0.5rem 0.85rem',
            borderRadius: 'var(--radius-full)',
            border: '1px solid var(--border-glass)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.85rem',
            fontSize: '0.725rem',
            color: '#cbd5e1',
            zIndex: 20,
          }}
        >
          <span style={{ color: 'var(--neon-cyan)', fontWeight: 700 }}>
            [ 3D ORBIT: DRAG TO ROTATE 360&deg; &bull; SCROLL TO ZOOM ]
          </span>
        </div>
      </div>
    </div>
  );
}
