import React, { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

/**
 * Premium 3D Alpha Pro MENA Atmospheric Background
 * 
 * Concept:
 * - Dark near-black backdrop (#08090C to #0E0F14)
 * - Large subtle 3D extruded Alpha Pro MENA logo sitting in depth behind the form
 * - Soft depth lighting & warm beige/gold atmospheric highlights
 * - Interactive subtle parallax tilt reacting to cursor motion
 * - Mobile optimized (simplified static depth for performance & battery)
 * - Strict Brand Kit fidelity: Authentic Crimson (#FF1E57) and Neutral (#F3F2F1)
 */
export const Login3DBackground: React.FC = () => {
  const [isMobile, setIsMobile] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  // Mouse position normalized (-0.5 to +0.5)
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Smooth spring physics for silky 60fps response
  const springConfig = { damping: 25, stiffness: 90, mass: 0.5 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  // Subtle 3D rotations (max ~6 degrees to maintain enterprise elegance)
  const rotateX = useTransform(smoothY, [-0.5, 0.5], [6, -6]);
  const rotateY = useTransform(smoothX, [-0.5, 0.5], [-8, 8]);
  const translateX = useTransform(smoothX, [-0.5, 0.5], [-15, 15]);
  const translateY = useTransform(smoothY, [-0.5, 0.5], [-12, 12]);

  // Ambient light flare follows opposite mouse angle
  const flareX = useTransform(smoothX, [-0.5, 0.5], ['35%', '65%']);
  const flareY = useTransform(smoothY, [-0.5, 0.5], ['30%', '70%']);

  useEffect(() => {
    const checkViewport = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkViewport();
    window.addEventListener('resize', checkViewport);

    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mql.matches);
    const motionListener = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mql.addEventListener('change', motionListener);

    const handleMouseMove = (e: MouseEvent) => {
      if (window.innerWidth < 768) return;
      const x = (e.clientX / window.innerWidth) - 0.5;
      const y = (e.clientY / window.innerHeight) - 0.5;
      mouseX.set(x);
      mouseY.set(y);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => {
      window.removeEventListener('resize', checkViewport);
      mql.removeEventListener('change', motionListener);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [mouseX, mouseY]);

  // 3D Extrusion slices (from deepest background layer to front face)
  const extrusionLayers = isMobile || prefersReducedMotion 
    ? [0, 8] // 2 lightweight layers on mobile
    : [-24, -18, -12, -6, 0, 6, 12, 18]; // 8 depth layers on desktop

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: 0,
        backgroundColor: '#090A0E',
      }}
      aria-hidden="true"
    >
      {/* ── 1. Deep Atmospheric Lighting & Radial Sheen ── */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: `
            radial-gradient(ellipse 90% 80% at 50% -10%, rgba(220, 185, 120, 0.08) 0%, transparent 60%),
            radial-gradient(circle 600px at 80% 20%, rgba(255, 30, 87, 0.05) 0%, transparent 70%),
            radial-gradient(circle 700px at 20% 80%, rgba(200, 160, 90, 0.06) 0%, transparent 70%),
            linear-gradient(180deg, #090A0E 0%, #0D0E13 50%, #08090C 100%)
          `,
        }}
      />

      {/* ── 2. Subtle Geometric Grid Floor Accent ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          width: '100%',
          height: '45%',
          background: `
            linear-gradient(180deg, transparent 0%, rgba(220, 185, 120, 0.015) 100%),
            repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.012) 0px, rgba(255, 255, 255, 0.012) 1px, transparent 1px, transparent 60px)
          `,
          maskImage: 'linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%)',
          WebkitMaskImage: 'linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%)',
        }}
      />

      {/* ── 3. Dynamic Ambient Gold Light Halo ── */}
      <motion.div
        style={{
          position: 'absolute',
          top: '40%',
          left: '50%',
          width: '560px',
          height: '560px',
          borderRadius: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle, rgba(225, 190, 125, 0.09) 0%, rgba(255, 30, 87, 0.04) 40%, transparent 70%)',
          filter: 'blur(45px)',
        }}
      />

      {/* ── 4. The 3D Extruded Brand Mark Stage ── */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: '100%',
          maxWidth: '680px',
          height: '460px',
          transform: 'translate(-50%, -50%)',
          perspective: '1200px',
          perspectiveOrigin: '50% 50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <motion.div
          style={{
            width: isMobile ? '320px' : '480px',
            height: isMobile ? '230px' : '345px',
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
                  translateZ: [0, 8, 0],
                }
          }
          transition={{
            duration: 7,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          {/* Multi-slice physical extrusion stack */}
          {extrusionLayers.map((zOffset, index) => {
            const isFront = index === extrusionLayers.length - 1;
            const depthFactor = (index + 1) / extrusionLayers.length;
            // Darkness multiplier for sides to create realistic ambient occlusion
            const sideCrimson = `rgb(${Math.round(255 * (0.35 + 0.65 * depthFactor))}, ${Math.round(30 * depthFactor)}, ${Math.round(87 * depthFactor)})`;
            const sideNeutral = `rgb(${Math.round(243 * (0.2 + 0.8 * depthFactor))}, ${Math.round(242 * (0.2 + 0.8 * depthFactor))}, ${Math.round(241 * (0.2 + 0.8 * depthFactor))})`;

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
                  opacity: isFront ? 0.32 : 0.18 + 0.12 * depthFactor,
                  filter: isFront
                    ? 'drop-shadow(0px 20px 40px rgba(0, 0, 0, 0.75)) drop-shadow(0px 0px 30px rgba(220, 185, 120, 0.15))'
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
                    filter: isFront ? 'url(#frontLighting)' : 'none',
                  }}
                >
                  <defs>
                    <linearGradient id={`crimsonGrad_${index}`} x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#FF3366" />
                      <stop offset="60%" stopColor="#FF1E57" />
                      <stop offset="100%" stopColor="#C40E3E" />
                    </linearGradient>
                    <linearGradient id={`neutralGrad_${index}`} x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#FFFFFF" />
                      <stop offset="50%" stopColor="#F3F2F1" />
                      <stop offset="100%" stopColor="#B3B0AD" />
                    </linearGradient>
                    {isFront && (
                      <filter id="frontLighting" x="-20%" y="-20%" width="140%" height="140%">
                        <feGaussianBlur in="SourceAlpha" stdDeviation="1.5" result="blur" />
                        <feSpecularLighting
                          in="blur"
                          surfaceScale="3"
                          specularConstant="1.2"
                          specularExponent="20"
                          lightingColor="#FFEED0"
                          result="specular"
                        >
                          <fePointLight x="40" y="-20" z="80" />
                        </feSpecularLighting>
                        <feComposite in="specular" in2="SourceAlpha" operator="in" result="specularResult" />
                        <feComposite in="SourceGraphic" in2="specularResult" operator="over" />
                      </filter>
                    )}
                  </defs>

                  {/* Left Loop — Official Brand Crimson (#FF1E57) */}
                  <path
                    d="M20 8 C9 8 2 15 2 26 L2 46 C2 57 9 64 20 64 L38 64 C49 64 56 57 56 46 L56 36 L44 36 L44 46 C44 50 41 53 36 53 L22 53 C17 53 14 50 14 46 L14 26 C14 22 17 19 22 19 L38 19 C43 19 46 22 46 26 L46 29 L58 29 L58 26 C58 15 51 8 40 8 Z"
                    fill={isFront ? `url(#crimsonGrad_${index})` : sideCrimson}
                  />

                  {/* Right Loop — Authentic Neutral (#F3F2F1) */}
                  <path
                    d="M62 8 C51 8 44 15 44 26 L44 36 L56 36 L56 26 C56 22 59 19 64 19 L78 19 C83 19 86 22 86 26 L86 46 C86 50 83 53 78 53 L62 53 C57 53 54 50 54 46 L54 43 L42 43 L42 46 C42 57 49 64 60 64 L80 64 C91 64 98 57 98 46 L98 26 C98 15 91 8 80 8 Z"
                    fill={isFront ? `url(#neutralGrad_${index})` : sideNeutral}
                  />
                </svg>
              </div>
            );
          })}
        </motion.div>
      </div>

      {/* ── 5. Elegant Soft Vignette & Radial Edge Shadow ── */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'radial-gradient(ellipse at center, transparent 35%, rgba(6, 7, 10, 0.75) 100%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
};
