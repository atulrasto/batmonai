import { api } from './client'

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

async function downloadPdf(url: string, filename: string): Promise<void> {
  const resp = await api.get(url, { responseType: 'blob' })
  const blob = new Blob([resp.data as BlobPart], { type: 'application/pdf' })
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(objectUrl)
}

export const downloadBatteryPdf = (batteryId: string, reportDate: Date) =>
  downloadPdf(
    `/reports/battery/${batteryId}/pdf?report_date=${isoDate(reportDate)}`,
    `battery_report_${isoDate(reportDate)}.pdf`,
  )

export const downloadAcChannelPdf = (channelId: string, reportDate: Date) =>
  downloadPdf(
    `/reports/ac-channel/${channelId}/pdf?report_date=${isoDate(reportDate)}`,
    `ac_report_${isoDate(reportDate)}.pdf`,
  )

export const emailBatteryReport = (batteryId: string, reportDate: Date) =>
  api.post(`/reports/battery/${batteryId}/email`, null, {
    params: { report_date: isoDate(reportDate) },
  }).then(r => r.data as { sent_to: string; filename: string })

export const emailAcChannelReport = (channelId: string, reportDate: Date) =>
  api.post(`/reports/ac-channel/${channelId}/email`, null, {
    params: { report_date: isoDate(reportDate) },
  }).then(r => r.data as { sent_to: string; filename: string })
