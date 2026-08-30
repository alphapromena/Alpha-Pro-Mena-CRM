import React, { useId } from 'react';

export type BrandLogoVariant = 'horizontal' | 'stacked' | 'mark';
export type BrandLogoTheme = 'dark-bg' | 'light-bg' | 'dark' | 'light' | 'auto';

export interface BrandLogoProps {
  variant?: BrandLogoVariant;
  theme?: BrandLogoTheme;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number;
  is3D?: boolean;
  className?: string;
  showTagline?: boolean;
}

/**
 * Official Alpha Pro MENA Brand Logo & Mark Component
 * Strictly matching the official Alpha Pro MENA Branding Kit.
 * 
 * EXACT BRAND KIT SPECIFICATIONS:
 * -------------------------------------------------------------
 * - Primary pink/red:      #FF1E57
 * - Secondary red:         #E92156
 * - Accent maroon:         #B7274F
 * - Dark charcoal (bg):    #313234
 * - Off-white (light bg):  #F3F2F1
 * - Pure black:            #000000
 * 
 * USAGE RULES:
 * - On DARK backgrounds ('dark-bg' / 'dark'):
 *     Mark: #FF1E57 (left loop) + #F3F2F1/white (right loop)
 *     Wordmark "ALPHA PRO": #FFFFFF (Barlow Bold/ExtraBold)
 *     Wordmark "MENA": #FFFFFF or #F3F2F1 (Barlow Regular/Medium, letter-spaced)
 * 
 * - On LIGHT backgrounds ('light-bg' / 'light'):
 *     Mark: #FF1E57 (left loop) + #313234/black (right loop)
 *     Wordmark "ALPHA PRO": #313234 (Barlow Bold/ExtraBold)
 *     Wordmark "MENA": #313234 (Barlow Regular/Medium, letter-spaced)
 * 
 * 3D ENHANCEMENT:
 * - Preserves physical depth and specular highlights via multi-stop SVG gradients
 *   and ambient lighting strictly derived from the brand kit's exact hex values.
 */
export const BrandLogoMark: React.FC<{
  size?: number | string;
  theme?: BrandLogoTheme;
  is3D?: boolean;
  className?: string;
}> = ({ size = 36, theme = 'dark-bg', is3D = true, className = '' }) => {
  const uniqueId = useId().replace(/:/g, '_');
  const pixelSize = typeof size === 'number' ? size : 36;
  const isLightBg = theme === 'light-bg' || theme === 'light';

  // SVG dimensions (standard 100 x 72 viewBox)
  const width = pixelSize;
  const height = pixelSize * 0.72;

  const crimsonGradId = `crimson_3d_${uniqueId}`;
  const neutralGradId = `neutral_3d_${uniqueId}`;
  const filterId = `bevel_3d_${uniqueId}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 100 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{
        display: 'inline-block',
        verticalAlign: 'middle',
        flexShrink: 0,
        filter: is3D ? 'drop-shadow(0px 2px 4px rgba(0, 0, 0, 0.45))' : 'none',
      }}
      aria-label="Alpha Pro MENA Logo Mark"
    >
      <defs>
        {is3D ? (
          <>
            {/* Left Loop: Brand Crimson with depth derived from #FF1E57 -> #E92156 -> #B7274F */}
            <linearGradient id={crimsonGradId} x1="15%" y1="0%" x2="85%" y2="100%">
              <stop offset="0%" stopColor="#FF386B" />
              <stop offset="35%" stopColor="#FF1E57" />
              <stop offset="70%" stopColor="#E92156" />
              <stop offset="100%" stopColor="#B7274F" />
            </linearGradient>

            {/* Right Loop: Dark-bg (#FFFFFF -> #F3F2F1 -> #313234) vs Light-bg (#313234 -> #1C1917 -> #000000) */}
            {isLightBg ? (
              <linearGradient id={neutralGradId} x1="15%" y1="0%" x2="85%" y2="100%">
                <stop offset="0%" stopColor="#45474A" />
                <stop offset="40%" stopColor="#313234" />
                <stop offset="85%" stopColor="#1C1917" />
                <stop offset="100%" stopColor="#000000" />
              </linearGradient>
            ) : (
              <linearGradient id={neutralGradId} x1="15%" y1="0%" x2="85%" y2="100%">
                <stop offset="0%" stopColor="#FFFFFF" />
                <stop offset="45%" stopColor="#F3F2F1" />
                <stop offset="80%" stopColor="#D8D5D2" />
                <stop offset="100%" stopColor="#313234" />
              </linearGradient>
            )}

            {/* Specular Lighting for premium tactile feel */}
            <filter id={filterId} x="-15%" y="-15%" width="130%" height="130%">
              <feGaussianBlur in="SourceAlpha" stdDeviation="0.8" result="blur" />
              <feSpecularLighting
                in="blur"
                surfaceScale="2.5"
                specularConstant="0.9"
                specularExponent="20"
                lightingColor="#FFFFFF"
                result="specular"
              >
                <fePointLight x="30" y="-10" z="60" />
              </feSpecularLighting>
              <feComposite in="specular" in2="SourceAlpha" operator="in" result="specularResult" />
              <feComposite in="SourceGraphic" in2="specularResult" operator="over" />
            </filter>
          </>
        ) : null}
      </defs>

      {/* ── Left Loop — Brand Crimson (#FF1E57) ─────────────────────────── */}
      <path
        d="M20 8 C9 8 2 15 2 26 L2 46 C2 57 9 64 20 64 L38 64 C49 64 56 57 56 46 L56 36 L44 36 L44 46 C44 50 41 53 36 53 L22 53 C17 53 14 50 14 46 L14 26 C14 22 17 19 22 19 L38 19 C43 19 46 22 46 26 L46 29 L58 29 L58 26 C58 15 51 8 40 8 Z"
        fill={is3D ? `url(#${crimsonGradId})` : '#FF1E57'}
        filter={is3D ? `url(#${filterId})` : undefined}
      />

      {/* ── Right Loop — Neutral (#F3F2F1 on dark / #313234 on light) ───── */}
      <path
        d="M62 8 C51 8 44 15 44 26 L44 36 L56 36 L56 26 C56 22 59 19 64 19 L78 19 C83 19 86 22 86 26 L86 46 C86 50 83 53 78 53 L62 53 C57 53 54 50 54 46 L54 43 L42 43 L42 46 C42 57 49 64 60 64 L80 64 C91 64 98 57 98 46 L98 26 C98 15 91 8 80 8 Z"
        fill={is3D ? `url(#${neutralGradId})` : isLightBg ? '#313234' : '#F3F2F1'}
        filter={is3D ? `url(#${filterId})` : undefined}
      />
    </svg>
  );
};

export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = 'horizontal',
  theme = 'dark-bg',
  size = 'md',
  is3D = true,
  className = '',
}) => {
  const sizeMap = {
    xs: { mark: 22, title: '13px', sub: '8.5px', gap: '6px' },
    sm: { mark: 28, title: '16px', sub: '10px', gap: '8px' },
    md: { mark: 36, title: '20px', sub: '11px', gap: '10px' },
    lg: { mark: 48, title: '26px', sub: '13px', gap: '12px' },
    xl: { mark: 64, title: '34px', sub: '16px', gap: '14px' },
  };

  const currentSize = typeof size === 'number'
    ? {
        mark: size,
        title: `${Math.round(size * 0.55)}px`,
        sub: `${Math.round(size * 0.28)}px`,
        gap: `${Math.round(size * 0.25)}px`,
      }
    : sizeMap[size] || sizeMap.md;

  const isLightBg = theme === 'light-bg' || theme === 'light';
  const textColor = isLightBg ? '#313234' : '#FFFFFF';
  const subTextColor = isLightBg ? '#313234' : '#FFFFFF';

  // Mark-only variant
  if (variant === 'mark') {
    return <BrandLogoMark size={currentSize.mark} theme={theme} is3D={is3D} className={className} />;
  }

  // Stacked variant (Mark on top, centered wordmark below)
  if (variant === 'stacked') {
    return (
      <div
        className={`brand-logo-stacked ${className}`}
        style={{
          display: 'inline-flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: currentSize.gap,
          userSelect: 'none',
        }}
      >
        <BrandLogoMark size={currentSize.mark * 1.3} theme={theme} is3D={is3D} />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div
            style={{
              fontFamily: "'Barlow', 'Inter', sans-serif",
              fontSize: currentSize.title,
              fontWeight: 800,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: textColor,
              lineHeight: 1.1,
            }}
          >
            Alpha Pro
          </div>
          <div
            style={{
              fontFamily: "'Barlow', 'Inter', sans-serif",
              fontSize: currentSize.sub,
              fontWeight: 500,
              letterSpacing: '0.36em',
              textTransform: 'uppercase',
              color: subTextColor,
              opacity: isLightBg ? 0.8 : 0.85,
              marginTop: '3px',
              paddingInlineStart: '0.36em', // Balances letter-spacing centering
            }}
          >
            MENA
          </div>
        </div>
      </div>
    );
  }

  // Horizontal variant (Mark on left, wordmark on right)
  return (
    <div
      className={`brand-logo-horizontal ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: currentSize.gap,
        userSelect: 'none',
      }}
    >
      <BrandLogoMark size={currentSize.mark} theme={theme} is3D={is3D} />
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div
          style={{
            fontFamily: "'Barlow', 'Inter', sans-serif",
            fontSize: currentSize.title,
            fontWeight: 800,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: textColor,
            lineHeight: 1.1,
          }}
        >
          Alpha Pro
        </div>
        <div
          style={{
            fontFamily: "'Barlow', 'Inter', sans-serif",
            fontSize: currentSize.sub,
            fontWeight: 500,
            letterSpacing: '0.32em',
            textTransform: 'uppercase',
            color: subTextColor,
            opacity: isLightBg ? 0.8 : 0.85,
            lineHeight: 1,
            marginTop: '3px',
            paddingInlineStart: '0.32em', // Balances letter-spacing
          }}
        >
          MENA
        </div>
      </div>
    </div>
  );
};
