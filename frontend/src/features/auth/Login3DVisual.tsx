import React, { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

/**
 * Premium 3D Alpha Pro MENA Brand Sculpture — Right Stage Component
 * 
 * Design Philosophy:
 * - Apple / Enterprise luxury product presentation aesthetic
 * - 100% Authentic Brand Kit fidelity: Official Crimson (#FF1E57) & Metallic Neutral (#F3F2F1)
 * - Multi-layer isometric 3D extrusion with realistic depth shadows and specular lighting
 * - Interactive cursor-driven parallax tilt + slow organic floating animation
 * - Zero heavy dependencies (GPU-accelerated CSS 3D + Framer Motion spring physics)
 */
export const Login3DVisual: React.FC = () => {
  const [isMobile, setIsMobile] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  // Mouse coordinates normalized (-0.5 to 0.5)
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Ultra-smooth spring physics for tactile enterprise feel
  const springConfig = { damping: 28, stiffness: 80, mass: 0.6 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  // Controlled, subtle 3D rotational tilt (max ~7 deg)
  const rotateX = useTransform(smoothY, [-0.5, 0.5], [7, -7]);
  const rotateY = useTransform(smoothX, [-0.5, 0.5], [-9, 9]);
  const translateX = useTransform(smoothX, [-0.5, 0.5], [-16, 16]);
  const translateY = useTransform(smoothY, [-0.5, 0.5], [-14, 14]);

  // Light reflection sheen follows the inverse mouse angle
  const sheenX = useTransform(smoothX, [-0.5, 0.5], ['20%', '80%']);
  const sheenY = useTransform(smoothY, [-0.5, 0.5], ['20%', '80%']);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 992);
    };
    handleResize();
    window.addEventListener('resize', handleResize);

    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mql.matches);
    const motionListener = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mql.addEventListener('change', motionListener);

    const handleMouseMove = (e: MouseEvent) => {
      if (window.innerWidth < 992) return;
      const x = (e.clientX / window.innerWidth) - 0.5;
      const y = (e.clientY / window.innerHeight) - 0.5;
      mouseX.set(x);
      mouseY.set(y);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => {
      window.removeEventListener('resize', handleResize);
      mql.removeEventListener('change', motionListener);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [mouseX, mouseY]);

  // Extrusion depth slices (from back to front facet)
  const extrusionLayers = isMobile || prefersReducedMotion
    ? [-12, 0, 12]
    : [-36, -28, -20, -12, -4, 4, 12, 20, 28];

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        userSelect: 'none',
        overflow: 'hidden',
      }}
    >
      {/* ── 1. Atmosphere: Luxury Gold & Crimson Lighting Points ── */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: isMobile ? '360px' : '620px',
          height: isMobile ? '360px' : '620px',
          borderRadius: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle at 45% 45%, rgba(212, 175, 55, 0.12) 0%, rgba(255, 30, 87, 0.06) 45%, transparent 70%)',
          filter: 'blur(55px)',
          pointerEvents: 'none',
        }}
      />

      {/* ── 2. Subtle Precision Radial Rings ── */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: isMobile ? '320px' : '540px',
          height: isMobile ? '320px' : '540px',
          transform: 'translate(-50%, -50%)',
          borderRadius: '50%',
          border: '1px dashed rgba(212, 175, 55, 0.08)',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: isMobile ? '420px' : '700px',
          height: isMobile ? '420px' : '700px',
          transform: 'translate(-50%, -50%)',
          borderRadius: '50%',
          border: '1px solid rgba(255, 255, 255, 0.03)',
          pointerEvents: 'none',
        }}
      />

      {/* ── 3. The 3D Floating Stage ── */}
      <div
        style={{
          perspective: '1300px',
          perspectiveOrigin: '50% 50%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          zIndex: 2,
        }}
      >
        <motion.div
          style={{
            width: isMobile ? '280px' : '480px',
            height: isMobile ? '200px' : '345px',
            position: 'relative',
            transformStyle: 'preserve-3d',
            rotateX: isMobile || prefersReducedMotion ? 0 : rotateX,
            rotateY: isMobile || prefersReducedMotion ? 0 : rotateY,
            x: isMobile || prefersReducedMotion ? 0 : translateX,
            y: isMobile || prefersReducedMotion ? 0 : translateY,
          }}
          animate={
            prefersReducedMotion || isMobile
              ? {}
              : {
                  y: [-8, 8, -8],
                  rotateZ: [-0.6, 0.6, -0.6],
                }
          }
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          {/* Multi-slice physical extrusion layers */}
          {extrusionLayers.map((zOffset, index) => {
            const isFront = index === extrusionLayers.length - 1;
            const depthRatio = (index + 1) / extrusionLayers.length;

            // Ambient occlusion shadow colors for side extrusion walls
            const sideCrimson = `rgb(${Math.round(255 * (0.35 + 0.65 * depthRatio))}, ${Math.round(30 * depthRatio)}, ${Math.round(87 * depthRatio)})`;
            const sideNeutral = `rgb(${Math.round(243 * (0.25 + 0.75 * depthRatio))}, ${Math.round(242 * (0.25 + 0.75 * depthRatio))}, ${Math.round(241 * (0.25 + 0.75 * depthRatio))})`;

            return (
              <div
                key={zOffset}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  transform: `translateZ(${zOffset}px)`,
                  opacity: isFront ? 1 : 0.45 + 0.45 * depthRatio,
                  filter: isFront
                    ? 'drop-shadow(0px 30px 60px rgba(0, 0, 0, 0.85)) drop-shadow(0px 0px 45px rgba(212, 175, 55, 0.2))'
                    : 'none',
                }}
              >
                <svg
                  viewBox="0 0 100 72"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  style={{
                    width: '100%',
                    height: '100%',
                    filter: isFront ? 'url(#frontLighting3D)' : 'none',
                  }}
                >
                  <defs>
                    <linearGradient id={`crimsonFacet_${index}`} x1="10%" y1="0%" x2="90%" y2="100%">
                      <stop offset="0%" stopColor="#FF1E57" />
                      <stop offset="45%" stopColor="#E92156" />
                      <stop offset="100%" stopColor="#B7274F" />
                    </linearGradient>
                    <linearGradient id={`neutralFacet_${index}`} x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#FFFFFF" />
                      <stop offset="45%" stopColor="#F3F2F1" />
                      <stop offset="100%" stopColor="#313234" />
                    </linearGradient>
                    {isFront && (
                      <filter id="frontLighting3D" x="-20%" y="-20%" width="140%" height="140%">
                        <feGaussianBlur in="SourceAlpha" stdDeviation="1.2" result="blur" />
                        <feSpecularLighting
                          in="blur"
                          surfaceScale="4.5"
                          specularConstant="1.4"
                          specularExponent="26"
                          lightingColor="#FFFFFF"
                          result="specular"
                        >
                          <fePointLight x="35" y="-15" z="90" />
                        </feSpecularLighting>
                        <feComposite in="specular" in2="SourceAlpha" operator="in" result="specularResult" />
                        <feComposite in="SourceGraphic" in2="specularResult" operator="over" />
                      </filter>
                    )}
                  </defs>

                  {/* Left Loop — Official Brand Crimson (#FF1E57) */}
                  <path
                    d="M20 8 C9 8 2 15 2 26 L2 46 C2 57 9 64 20 64 L38 64 C49 64 56 57 56 46 L56 36 L44 36 L44 46 C44 50 41 53 36 53 L22 53 C17 53 14 50 14 46 L14 26 C14 22 17 19 22 19 L38 19 C43 19 46 22 46 26 L46 29 L58 29 L58 26 C58 15 51 8 40 8 Z"
                    fill={isFront ? `url(#crimsonFacet_${index})` : sideCrimson}
                  />

                  {/* Right Loop — Authentic Neutral (#F3F2F1) */}
                  <path
                    d="M62 8 C51 8 44 15 44 26 L44 36 L56 36 L56 26 C56 22 59 19 64 19 L78 19 C83 19 86 22 86 26 L86 46 C86 50 83 53 78 53 L62 53 C57 53 54 50 54 46 L54 43 L42 43 L42 46 C42 57 49 64 60 64 L80 64 C91 64 98 57 98 46 L98 26 C98 15 91 8 80 8 Z"
                    fill={isFront ? `url(#neutralFacet_${index})` : sideNeutral}
                  />
                </svg>
              </div>
            );
          })}
        </motion.div>

        {/* ── 4. Elegant Brand Caption Under 3D Sculpture ── */}
        <div
          style={{
            marginTop: isMobile ? '20px' : '36px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <div
            style={{
              fontFamily: "'Barlow', sans-serif",
              fontSize: isMobile ? '20px' : '28px',
              fontWeight: 800,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: '#FFFFFF',
              lineHeight: 1.1,
            }}
          >
            Alpha Pro
          </div>
          <div
            style={{
              fontFamily: "'Barlow', sans-serif",
              fontSize: isMobile ? '11px' : '13px',
              fontWeight: 500,
              letterSpacing: '0.36em',
              textTransform: 'uppercase',
              color: '#F3F2F1',
              opacity: 0.9,
              paddingInlineStart: '0.36em',
            }}
          >
            MENA
          </div>
        </div>
      </div>

      {/* ── 5. Bottom Vignette Gradient ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          width: '100%',
          height: '35%',
          background: 'linear-gradient(to top, rgba(9, 10, 14, 0.8) 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
};
