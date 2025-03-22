function treeNav() {
  return {
    nodes: [
      {
        title: "Dashboard",
        path: "/",
        children: [],
        expanded: false
      },
      {
        title: "Config",
        path: "/config",
        children: [],
        expanded: false
      },
      {
        title: "Apps",
        path: "/apps",
        children: [
          { title: "ayso", path: "/configs/ayso" },
          { title: "rems", path: "/configs/rems" }
        ],
        expanded: false
      }
    ],
    initTree() {
      // Initialize tree state
    },
    toggleNode(node) {
      node.expanded = !node.expanded;
    },
    navigate(path) {
      window.location.href = path;
    },
    isCurrent(path) {
      return window.location.pathname === path;
    }
  };
}