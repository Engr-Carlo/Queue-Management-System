# Queue Management System - Design System Documentation

## Overview
The Queue Management System has been redesigned with a modern, cohesive blue-themed design system. This document outlines the design principles, color palette, components, and usage guidelines.

---

## 🎨 Color Palette

### Primary Color (Blue)
- **Primary**: `#3b82f6` (rgb(59, 130, 246)) - Main brand color
- **Primary Dark**: `#1d4ed8` (rgb(29, 78, 216)) - Hover states, emphasis
- **Primary Light**: `#60a5fa` (rgb(96, 165, 250)) - Accents
- **Primary Lighter**: `#dbeafe` (rgb(219, 234, 254)) - Backgrounds, badges

### Neutral Colors
- **Dark**: `#1e293b` (rgb(30, 41, 59)) - Headers, primary text
- **Neutral**: `#475569` (rgb(71, 85, 105)) - Body text
- **Light**: `#cbd5e1` (rgb(203, 213, 225)) - Borders
- **Lighter**: `#f1f5f9` (rgb(241, 245, 249)) - Subtle backgrounds
- **Lightest**: `#f8fafc` (rgb(248, 250, 252)) - Page backgrounds
- **White**: `#ffffff` - Cards, containers

### Status Colors
- **Success**: `#10b981` - Completed actions, positive states
- **Warning**: `#f59e0b` - Alerts, waiting states
- **Error**: `#ef4444` - Errors, critical states

---

## 📏 Spacing Scale

Based on 8px grid system:
- `--space-1`: 4px
- `--space-2`: 8px
- `--space-3`: 12px
- `--space-4`: 16px (base)
- `--space-5`: 24px
- `--space-6`: 32px
- `--space-8`: 48px
- `--space-10`: 64px

---

## 🔤 Typography

### Font Family
- **Primary**: Inter (Google Fonts)
- **Fallback**: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif

### Font Sizes
- `--font-size-xs`: 12px
- `--font-size-sm`: 14px
- `--font-size-base`: 16px (body text)
- `--font-size-lg`: 18px
- `--font-size-xl`: 20px
- `--font-size-2xl`: 24px
- `--font-size-3xl`: 30px
- `--font-size-4xl`: 36px
- `--font-size-5xl`: 48px
- `--font-size-6xl`: 64px

### Font Weights
- **Normal**: 400
- **Medium**: 500
- **Semibold**: 600 (buttons, labels)
- **Bold**: 700 (headings)
- **Extrabold**: 800 (page titles)

---

## 🧩 Components

### Buttons

#### Primary Button
```html
<button class="btn btn-primary">Click Me</button>
```
- Blue gradient background
- White text
- Hover: Lift effect + darker gradient
- Use for: Primary CTAs, submit actions

#### Secondary Button
```html
<button class="btn btn-secondary">Cancel</button>
```
- Light gray background
- Dark text, bordered
- Hover: Darker gray
- Use for: Secondary actions, cancel

#### Button Sizes
- `.btn-sm` - Compact buttons
- `.btn` - Default size
- `.btn-lg` - Large buttons

### Cards

```html
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Title</h3>
    <p class="card-subtitle">Subtitle</p>
  </div>
  <p>Card content...</p>
</div>
```

- White background
- 16px border radius
- 24px padding
- Hover: Lift + shadow increase
- `.card-compact` for less padding

### Badges

```html
<span class="badge badge-primary">New</span>
<span class="badge badge-success">Active</span>
<span class="badge badge-warning">Pending</span>
<span class="badge badge-error">Error</span>
```

### Icons

Custom SVG icons located in `/images/icons/`:
- `ticket.svg` - Queue tickets
- `user.svg` - Persons/profiles
- `status.svg` - Status/clock
- `qr.svg` - QR codes
- `refresh.svg` - Refresh/reload
- `dashboard.svg` - Dashboard view
- `check.svg` - Success/confirmation
- `phone.svg` - Mobile device
- `calendar.svg` - Date/time
- `target.svg` - Targeting/focus
- `building.svg` - Institution/office
- `chart.svg` - Analytics
- `list.svg` - Lists/queues
- And more...

#### Usage with Icon Helper
```javascript
// Load icon into element
await QueueIcons.insert(document.getElementById('myIcon'), 'ticket', 'icon-lg');

// Get icon HTML
const iconHTML = await QueueIcons.get('user', 'icon text-primary');
```

#### Icon Sizes
- `.icon-sm` - 1.25rem (20px)
- `.icon` - 1.5rem (24px) - default
- `.icon-lg` - 2rem (32px)
- `.icon-xl` - 2.5rem (40px)

#### Icon Circles
```html
<div class="icon-circle">
  <svg class="icon">...</svg>
</div>
```
- Light blue background
- Primary blue icon color
- Perfect for feature highlights

---

## 📐 Layout

### Container
```html
<div class="container">
  <!-- Content -->
</div>
```
- Max-width: 1200px
- Responsive padding
- `.container-sm` - 640px max
- `.container-lg` - 1400px max

### Grid System
```html
<div class="grid grid-cols-3 gap-4">
  <div class="card">Item 1</div>
  <div class="card">Item 2</div>
  <div class="card">Item 3</div>
</div>
```

- `.grid-cols-2` - 2 columns
- `.grid-cols-3` - 3 columns
- `.grid-cols-4` - 4 columns
- Responsive: Single column on mobile

---

## 🖼️ Branding Assets

### Logo
- **Main Logo**: `/images/logo.svg` (200x200)
- Modern queue ticket design
- Blue gradient with white ticket
- Scalable SVG format

### Favicons
- `/images/favicon-16x16.svg` - Browser tabs
- `/images/favicon-32x32.svg` - Bookmarks
- `/images/apple-touch-icon.svg` - iOS home screen (180x180)

### Usage
```html
<head>
  <link rel="icon" type="image/svg+xml" href="images/favicon-32x32.svg">
  <link rel="apple-touch-icon" sizes="180x180" href="images/apple-touch-icon.svg">
</head>

<!-- In page -->
<img src="images/logo.svg" alt="Queue System" class="logo">
```

---

## 📱 Responsive Design

### Breakpoints
- **Mobile**: < 768px
- **Tablet**: 769px - 1024px
- **Desktop**: > 1024px

### Mobile Adaptations
- Single column layouts
- Reduced font sizes
- Compact padding/margins
- Touch-friendly button sizes (min 44px)

---

## ♿ Accessibility

### Guidelines
- Color contrast ratio: WCAG AA compliant
- Focus states on all interactive elements
- Semantic HTML5 elements
- ARIA labels where needed
- Keyboard navigation support

### Focus States
All interactive elements have visible focus indicators:
- Blue outline ring
- Increased contrast
- Keyboard accessible

---

## 🎭 Animation & Transitions

### Standard Transitions
- **Fast**: 150ms - Hover states, small changes
- **Base**: 200ms - Button clicks, color changes
- **Slow**: 300ms - Complex animations, page transitions

### Hover Effects
- Buttons: -2px translateY + shadow
- Cards: -2px translateY + shadow increase
- Icons: Scale 1.05

---

## 📋 Utility Classes

### Flexbox
- `.flex` - Display flex
- `.flex-col` - Flex direction column
- `.items-center` - Align items center
- `.justify-center` - Justify content center
- `.justify-between` - Space between
- `.gap-2`, `.gap-3`, `.gap-4` - Gap spacing

### Spacing
- `.mb-4`, `.mt-4` - Margin bottom/top
- `.p-4`, `.p-5`, `.p-6` - Padding

### Text
- `.text-center`, `.text-left`, `.text-right` - Alignment
- `.text-primary`, `.text-neutral` - Colors
- `.font-semibold`, `.font-bold` - Weights

---

## 🚀 Usage Examples

### Feature Card
```html
<div class="card">
  <div class="icon-circle icon-circle-lg mb-4">
    <svg class="icon icon-lg"><!-- icon SVG --></svg>
  </div>
  <h3 class="card-title">Queue Ticket</h3>
  <p class="card-subtitle">Generate your queue number</p>
  <button class="btn btn-primary mt-4">Get Started</button>
</div>
```

### Status Badge
```html
<div class="flex items-center gap-2">
  <span class="badge badge-success">Active</span>
  <span>Queue #A001</span>
</div>
```

### Page Header
```html
<header style="background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark)); padding: var(--space-5);">
  <div class="container flex items-center justify-between">
    <img src="images/logo.svg" alt="Logo" style="height: 40px;">
    <h1 style="color: white; margin: 0;">Queue Management System</h1>
  </div>
</header>
```

---

## 📝 Best Practices

1. **Always use CSS variables** from the design system for colors
2. **Use the 8px spacing scale** for consistent spacing
3. **Leverage utility classes** before writing custom CSS
4. **Maintain the 3-color limit**: Blue primary + 2 neutral shades
5. **Test on mobile devices** for touch targets and readability
6. **Use semantic HTML** for better accessibility
7. **Load custom icons** via the QueueIcons helper
8. **Apply hover states** to all interactive elements

---

## 🔄 Migration Notes

### Color Changes
- Red (#dc2626) → Blue (#3b82f6)
- Purple (#667eea) → Blue (#3b82f6)
- All gradient backgrounds updated to blue

### Logo Changes
- Queue-logo.jpg → logo.svg
- favicon.png → favicon-32x32.svg + multiple sizes

### Icon Changes
- Font Awesome → Custom SVG icons (where implemented)
- Smaller file sizes, better performance

---

## 🛠️ Development

### File Structure
```
/images/
  logo.svg                  # Main logo
  favicon-16x16.svg         # Small favicon
  favicon-32x32.svg         # Standard favicon
  apple-touch-icon.svg      # iOS icon
  /icons/                   # Custom icon library
    ticket.svg
    user.svg
    ...

style.css                   # Design system CSS
icons.js                    # Icon loader utility
```

### Adding New Icons
1. Create SVG in `/images/icons/`
2. Use `viewBox="0 0 24 24"` for consistency
3. Use `currentColor` for stroke/fill
4. Keep stroke-width at 2 for consistency
5. Load via `QueueIcons.load('icon-name')`

---

## 📞 Support

For design system questions or contributions:
- Developer: Engr. Carlo Cimacio
- Review this documentation before making changes
- Test all changes across mobile, tablet, and desktop

---

**Last Updated**: January 2026
**Version**: 2.0
**Theme**: Blue Professional
