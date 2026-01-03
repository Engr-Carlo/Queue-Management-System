// Icon Helper for Queue Management System
// Loads custom SVG icons from images/icons/

const QueueIcons = {
  // Cache for loaded icons
  cache: {},
  
  // Load an icon by name
  async load(iconName) {
    if (this.cache[iconName]) {
      return this.cache[iconName];
    }
    
    try {
      const response = await fetch(`images/icons/${iconName}.svg`);
      const svgText = await response.text();
      this.cache[iconName] = svgText;
      return svgText;
    } catch (error) {
      console.error(`Failed to load icon: ${iconName}`, error);
      return '';
    }
  },
  
  // Insert icon into element
  async insert(element, iconName, className = 'icon') {
    const svgText = await this.load(iconName);
    if (element && svgText) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = svgText.trim();
      const svg = tempDiv.firstChild;
      if (svg) {
        svg.setAttribute('class', className);
        element.innerHTML = '';
        element.appendChild(svg);
      }
    }
  },
  
  // Get inline SVG with class
  async get(iconName, className = 'icon') {
    const svgText = await this.load(iconName);
    if (svgText) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = svgText.trim();
      const svg = tempDiv.firstChild;
      if (svg) {
        svg.setAttribute('class', className);
        return svg.outerHTML;
      }
    }
    return '';
  }
};

// Make it globally available
window.QueueIcons = QueueIcons;
