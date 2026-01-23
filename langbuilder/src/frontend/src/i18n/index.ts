import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import resourcesToBackend from "i18next-resources-to-backend";

const loadResource = async (language: string, namespace: string) => {
  try {
    const module = await import(
      `./locales/${language}/${namespace}.json`
    );
    return module.default;   // 👈 THIS IS REQUIRED
  } catch {
    const module = await import(
      `./locales/en-US/${namespace}.json`
    );
    return module.default;   // 👈 THIS TOO
  }
};

i18n
  .use(resourcesToBackend(loadResource))
  .use(LanguageDetector)
  .use(initReactI18next) 
  .init({
    debug: false,
    fallbackLng: "en-US",
    ns: ["translation"],
    defaultNS: "translation",
    detection: {
      order: ["querystring", "localStorage", "navigator"],
      caches: ["localStorage"],
      lookupQuerystring: "lang",
      lookupLocalStorage: "locale",
    },
    interpolation: {
      escapeValue: false,
    },
    returnEmptyString: false,  // Return key when value is empty string
  });
  console.log("I18N INIT FILE LOADED");

  (window as any).i18n = i18n; // 👈 ADD THIS

export default i18n;
