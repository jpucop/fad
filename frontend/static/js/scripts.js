// static/app.js
document.addEventListener('alpine:init', () => {
  Alpine.data('treeNav', () => ({
    nodes: [
      {
        title: 'Dashboard',
        path: '/',
        expanded: true,
        children: []  // Populated dynamically below
      }
    ],
    initTree() {
      // Fetch app names from backend to populate nav
      fetch('/configs')
        .then(response => response.json())
        .then(data => {
          this.nodes[0].children = data.configs.map(config => ({
            title: config.app_name,
            path: `/app/${config.app_name}`
          }));
        });
    },
    toggleNode(node) {
      node.expanded = !node.expanded;
    },
    isCurrent(path) {
      return window.location.pathname === path;
    }
  }));
});