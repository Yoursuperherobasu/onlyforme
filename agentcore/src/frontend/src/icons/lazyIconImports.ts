// Export the lazy loading mapping for icons
export const lazyIconsMapping = {
  AIML: () => import("@/icons/AIML").then((mod) => ({ default: mod.AIMLIcon })),
  
  Google: () =>
    import("@/icons/Google").then((mod) => ({ default: mod.GoogleIcon })),
 
  GoogleGenerativeAI: () =>
    import("@/icons/GoogleGenerativeAI").then((mod) => ({
      default: mod.GoogleGenerativeAIIcon,
    })),
  
  Mcp: () => import("@/icons/MCP").then((mod) => ({ default: mod.McpIcon })),
  
  Pinecone: () =>
    import("@/icons/Pinecone").then((mod) => ({ default: mod.PineconeIcon })),
  
  };
