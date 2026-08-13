import axios from "axios";

export const api = axios.create({
  baseURL: "/",
});

export function downloadBlobUrl(blob: Blob): string {
  return URL.createObjectURL(blob);
}
