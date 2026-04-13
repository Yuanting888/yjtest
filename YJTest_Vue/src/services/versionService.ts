import packageJson from '../../package.json';
import { brandReleaseRepo } from '@/config/brand';

export interface VersionInfo {
  current: string;
  latest?: string;
  hasUpdate: boolean;
  releaseUrl?: string;
  releaseNotes?: string;
  checkTime?: Date;
}

const GITHUB_API_BASE = 'https://api.github.com';
const CHECK_INTERVAL = 1000 * 60 * 60;

let cachedVersionInfo: VersionInfo | null = null;
let lastCheckTime = 0;

export function getCurrentVersion(): string {
  return packageJson.version || '0.0.0';
}

export function compareVersions(v1: string, v2: string): number {
  const parts1 = v1.replace(/^v/, '').split('.').map(Number);
  const parts2 = v2.replace(/^v/, '').split('.').map(Number);

  for (let index = 0; index < Math.max(parts1.length, parts2.length); index += 1) {
    const left = parts1[index] || 0;
    const right = parts2[index] || 0;

    if (left > right) return 1;
    if (left < right) return -1;
  }

  return 0;
}

export async function checkLatestVersion(): Promise<VersionInfo> {
  const now = Date.now();

  if (cachedVersionInfo && now - lastCheckTime < CHECK_INTERVAL) {
    return cachedVersionInfo;
  }

  const current = getCurrentVersion();
  const versionInfo: VersionInfo = {
    current,
    hasUpdate: false,
  };

  if (!brandReleaseRepo) {
    return versionInfo;
  }

  try {
    const response = await fetch(`${GITHUB_API_BASE}/repos/${brandReleaseRepo}/releases/latest`, {
      headers: {
        Accept: 'application/vnd.github.v3+json',
      },
    });

    if (!response.ok) {
      return versionInfo;
    }

    const release = await response.json();
    const latestVersion = release.tag_name?.replace(/^v/, '') || '';

    versionInfo.latest = latestVersion;
    versionInfo.hasUpdate = compareVersions(latestVersion, current) > 0;
    versionInfo.releaseUrl = release.html_url;
    versionInfo.releaseNotes = release.body;
    versionInfo.checkTime = new Date();

    cachedVersionInfo = versionInfo;
    lastCheckTime = now;
  } catch (error) {
    console.warn('版本检查失败', error);
  }

  return versionInfo;
}

export function formatVersion(version: string): string {
  if (!version || version === '0.0.0') {
    return 'dev';
  }

  return `v${version.replace(/^v/, '')}`;
}
