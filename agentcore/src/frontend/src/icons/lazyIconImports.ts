// Export the lazy loading mapping for icons
export const lazyIconsMapping = {
  AIML: () => import("@/icons/AIML").then((mod) => ({ default: mod.AIMLIcon })),
  
 
  
  
  
  GoogleGenerativeAI: () =>
    import("@/icons/GoogleGenerativeAI").then((mod) => ({
      default: mod.GoogleGenerativeAIIcon,
    })),
  
  GradientInfinity: () =>
    import("@/icons/GradientSparkles").then((mod) => ({
      default: mod.GradientInfinity,
    })),
  
  
  GradientUngroup: () =>
    import("@/icons/GradientSparkles").then((mod) => ({
      default: mod.GradientUngroup,
    })),
  GradientSave: () =>
    import("@/icons/GradientSparkles").then((mod) => ({
      default: mod.GradientSave,
    })),
  
  Groq: () => import("@/icons/Groq").then((mod) => ({ default: mod.GroqIcon })),
  
  
  
  
  
  
  
 
 
  
  
  
 
};
