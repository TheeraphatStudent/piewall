export const GITHUB_URL = "https://github.com/TheeraphatStudent/piewall";
export const INSTALLER_URL = GITHUB_URL + "/releases/latest/download/piewall-setup.exe";
export const PORTABLE_URL = GITHUB_URL + "/releases/latest/download/piewall.exe";
export const MAC_ARM_URL = GITHUB_URL + "/releases/latest/download/piewall-macos-arm64.pkg";
export const MAC_INTEL_URL = GITHUB_URL + "/releases/latest/download/piewall-macos-x86_64.pkg";
// Stripe Payment Link, from site/.env (see .env.example). A production build without it fails
// instead of shipping a coffee button that goes nowhere.
export const COFFEE_URL: string = import.meta.env.PUBLIC_COFFEE_URL || "#coffee";
if (import.meta.env.PROD && !COFFEE_URL.startsWith("https://buy.stripe.com/")) {
  throw new Error("PUBLIC_COFFEE_URL must be a https://buy.stripe.com/ Payment Link (set it in site/.env)");
}
export const SITE_URL = "https://piewall.th33raphat.dev";

export const LICENSE_URL = GITHUB_URL + "/blob/main/LICENSE";
export const RELEASES_URL = GITHUB_URL + "/releases";
export const TAGLINE = "Your firewall, simple as pie.";
export const DESCRIPTION =
  "piewall shows every firewall rule on Windows and macOS in half a second, opens a port in one step, and finds the Block rules quietly overriding your Allow rules. Free and open source.";
