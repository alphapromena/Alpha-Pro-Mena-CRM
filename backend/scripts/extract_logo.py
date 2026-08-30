import fitz
import re

doc = fitz.open('c:/Users/user/Alpha-Pro-Mena-CRM/Alpha MENA Branding Kit (1).pdf')

# Let's render transparent crops of page 1 and page 2 for the logo
p1 = doc[0] # Dark version
p2 = doc[1] # Light version

# Tight bounding box for the full logo: x0=110, y0=280, x1=485, y1=760
clip_full = fitz.Rect(110, 280, 485, 760)
pix1 = p1.get_pixmap(dpi=300, clip=clip_full)
pix1.save('c:/Users/user/Alpha-Pro-Mena-CRM/frontend/public/logo-alpha-dark.png')

pix2 = p2.get_pixmap(dpi=300, clip=clip_full)
pix2.save('c:/Users/user/Alpha-Pro-Mena-CRM/frontend/public/logo-alpha-light.png')

# Tight bounding box for the mark only: x0=170, y0=295, x1=425, y1=460
clip_mark = fitz.Rect(170, 295, 425, 460)
pix_mark1 = p1.get_pixmap(dpi=300, clip=clip_mark)
pix_mark1.save('c:/Users/user/Alpha-Pro-Mena-CRM/frontend/public/logo-mark-dark.png')

pix_mark2 = p2.get_pixmap(dpi=300, clip=clip_mark)
pix_mark2.save('c:/Users/user/Alpha-Pro-Mena-CRM/frontend/public/logo-mark-light.png')

# Extract SVG paths
svg_text = p1.get_svg_image()
with open('c:/Users/user/Alpha-Pro-Mena-CRM/frontend/public/raw_page1.svg', 'w', encoding='utf-8') as f:
    f.write(svg_text)

# Let's find path definitions
d_paths = re.findall(r'd="([^"]+)"', svg_text)
print(f"Total d paths found: {len(d_paths)}")

# The two mark paths are the longest paths with coordinates around 900-1400
mark_paths = [p for p in d_paths if '961.41' in p or '1386' in p]
print(f"Mark paths found: {len(mark_paths)}")
for i, p in enumerate(mark_paths):
    print(f"Path {i+1} starts: {p[:60]}")

print("Successfully generated logo pngs and extracted paths!")
