import { api } from './client'

export interface FirmwareFile {
  path: string
  address: string
}

export interface FirmwareRelease {
  version: string
  description: string
  chip: string
  files: FirmwareFile[]
  built_at: string
  ready: boolean
}

export const listReleases = () =>
  api.get<FirmwareRelease[]>('/firmware/releases').then(r => r.data)

export const downloadFirmwareFile = async (
  version: string,
  filename: string
): Promise<Uint8Array> => {
  const r = await api.get<ArrayBuffer>(`/firmware/releases/${version}/${filename}`, {
    responseType: 'arraybuffer',
  })
  return new Uint8Array(r.data)
}
