import { Cookies } from "react-cookie";
import { SENSEI_ACCESS_TOKEN } from "@/constants/constants";

export const customGetAccessToken = () => {
  const cookies = new Cookies();
  return cookies.get(SENSEI_ACCESS_TOKEN);
};
