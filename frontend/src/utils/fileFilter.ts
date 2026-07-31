const HIDDEN_PATTERNS: RegExp[] = [
  /\.DS_Store$/i,
  /^Thumbs\.db$/i,
  /^__MACOSX\//i,
  /\.git\//i,
  /^node_modules\//i,
  /^\./,
]

/** 判断文件是否应被过滤(隐藏文件/系统文件)。 */
export function isHiddenFile(relativePath: string): boolean {
  return HIDDEN_PATTERNS.some((p) => p.test(relativePath))
}

/** 过滤掉隐藏/系统文件。 */
export function filterValidFiles(files: File[]): File[] {
  return files.filter((f) => {
    const path = (f as any).webkitRelativePath || f.name
    return !isHiddenFile(path)
  })
}
