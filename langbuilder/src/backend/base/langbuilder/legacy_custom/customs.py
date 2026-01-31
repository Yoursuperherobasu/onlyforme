from langbuilder.template import frontend_node

# These should always be instantiated
CUSTOM_NODES: dict[str, dict[str, frontend_node.base.FrontendNode]] = {
    "custom_components": {
        "ExecutableNode": frontend_node.custom_components.ExecutableNodeFrontendNode(),
    },
    "component": {
        "Node": frontend_node.custom_components.NodeFrontendNode(),
    },
}


def get_custom_nodes(node_type: str):
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
