import React, { useState, useEffect } from 'react';
import { BrandLogo } from '../common/BrandLogo';

interface LoadingScreenProps {
  message?: string;
  subMessage?: string;
}

/**
 * Premium Alpha Pro MENA Full-Screen Loading / Splash Screen
 * 
 * Features:
 * - Background Video "Wall" (seamless 1080p webm/mp4 loop, compressed to ~2MB)
 * - Autoplay, muted, infinite loop, playsInline for iOS / modern browsers
 * - Brand Dark Overlay (#313234 / pure black at ~50% opacity) for high legibility
 * - Solid fallback background (#313234) before video loads or on low-power devices
 * - 100% Brand Kit 3D Logo (#FF1E57 + #F3F2F1) & Barlow Typography
 * - Polished enterprise micro-animations & smooth progress indicator
 */
const LOADING_VIDEOS = [
  { webm: '/videos/wall.webm', mp4: '/videos/wall.mp4' },
  { webm: '/videos/wall2.webm', mp4: '/videos/wall2.mp4' },
];

export const LoadingScreen: React.FC<LoadingScreenProps> = ({
  message = 'Initializing Alpha Pro MENA CRM System...',
  subMessage = 'Enterprise Sales Outreach & Management Platform',
}) => {
  const [videoLoaded, setVideoLoaded] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const [videoIdx] = useState<number>(() => {
    const saved = localStorage.getItem('crm_loading_video_idx');
    const nextIdx = saved !== null ? (parseInt(saved, 10) + 1) % LOADING_VIDEOS.length : 0;
    localStorage.setItem('crm_loading_video_idx', nextIdx.toString());
    return nextIdx;
  });

  useEffect(() => {
    // If video takes more than 3s to trigger onLoadedData, graceful fallback is already in place
    const timer = setTimeout(() => {
      if (!videoLoaded) setVideoLoaded(true);
    }, 3000);
    return () => clearTimeout(timer);
  }, [videoLoaded]);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        backgroundColor: '#313234', // Brand kit dark charcoal fallback
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        zIndex: 99999,
        userSelect: 'none',
      }}
    >
      {/* ── 1. Full-Bleed Background Video with Enhanced Brightness ── */}
      {!videoError && (
        <video
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          onLoadedData={() => setVideoLoaded(true)}
          onError={() => setVideoError(true)}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            zIndex: 0,
            opacity: videoLoaded ? 1 : 0,
            filter: 'brightness(1.24) contrast(1.10) saturate(1.15)',
            transition: 'opacity 0.8s ease-in-out',
            pointerEvents: 'none',
          }}
        >
          <source src={LOADING_VIDEOS[videoIdx].webm} type="video/webm" />
          <source src={LOADING_VIDEOS[videoIdx].mp4} type="video/mp4" />
        </video>
      )}

      {/* ── 2. Dark Brand Semi-Transparent Overlay ─────────────────── */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(circle at center, rgba(49, 50, 52, 0.28) 0%, rgba(18, 19, 21, 0.58) 100%)',
          backdropFilter: 'blur(2px)',
          WebkitBackdropFilter: 'blur(2px)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      />

      {/* ── 3. Subtle Ambient Light Glows ───────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle, rgba(255, 30, 87, 0.12) 0%, rgba(212, 175, 55, 0.06) 40%, transparent 70%)',
          filter: 'blur(60px)',
          zIndex: 2,
          pointerEvents: 'none',
        }}
      />

      {/* ── 4. Foreground Content Container ─────────────────────────── */}
      <div
        style={{
          position: 'relative',
          zIndex: 3,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          padding: '24px',
          maxWidth: '460px',
          width: '90%',
        }}
      >
        {/* Official 3D Brand Logo */}
        <div style={{ marginBottom: '32px' }}>
          <BrandLogo variant="stacked" size="xl" theme="dark-bg" is3D={true} />
        </div>

        {/* Brand Pulsing Ring Indicator */}
        <div
          style={{
            position: 'relative',
            width: '44px',
            height: '44px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '24px',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '2px solid rgba(255, 30, 87, 0.25)',
              animation: 'pulseRing 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite',
            }}
          />
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              border: '3px solid transparent',
              borderTopColor: '#FF1E57', // Brand Crimson
              borderRightColor: '#F3F2F1', // Brand Neutral
              animation: 'spinLoader 0.9s cubic-bezier(0.55, 0.15, 0.45, 0.85) infinite',
            }}
          />
        </div>

        {/* Initialization Message */}
        <div
          style={{
            fontFamily: "'Barlow', sans-serif",
            fontSize: '15px',
            fontWeight: 600,
            color: '#FFFFFF',
            letterSpacing: '0.04em',
            marginBottom: '6px',
            textShadow: '0 2px 8px rgba(0, 0, 0, 0.5)',
          }}
        >
          {message}
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontFamily: "'Barlow', sans-serif",
            fontSize: '11px',
            fontWeight: 500,
            color: 'rgba(243, 242, 241, 0.65)',
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            marginBottom: '20px',
          }}
        >
          {subMessage}
        </div>

        {/* Sleek Progress Bar */}
        <div
          style={{
            width: '200px',
            height: '3px',
            backgroundColor: 'rgba(255, 255, 255, 0.12)',
            borderRadius: '99px',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              background: 'linear-gradient(90deg, #FF1E57 0%, #E92156 50%, #B7274F 100%)',
              borderRadius: '99px',
              boxShadow: '0 0 10px rgba(255, 30, 87, 0.5)',
              animation: 'indeterminateProgress 1.8s ease-in-out infinite',
            }}
          />
        </div>
      </div>

      {/* Keyframe Styles */}
      <style>{`
        @keyframes spinLoader {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulseRing {
          0% { transform: scale(0.85); opacity: 0.8; }
          50% { transform: scale(1.35); opacity: 0.15; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        @keyframes indeterminateProgress {
          0% { left: -40%; width: 40%; }
          50% { left: 30%; width: 60%; }
          100% { left: 100%; width: 40%; }
        }
      `}</style>
    </div>
  );
};
