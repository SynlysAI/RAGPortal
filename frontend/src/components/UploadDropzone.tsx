import { useDropzone } from 'react-dropzone'
import { UploadIcon } from 'lucide-react'

interface Props {
  onFiles: (files: File[]) => void
  maxSizeMb: number
  allowedTypes: string[]
  disabled?: boolean
}

export default function UploadDropzone({ onFiles, maxSizeMb, allowedTypes, disabled }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => { if (!disabled) onFiles(accepted) },
    disabled,
  })

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors
          ${disabled ? 'border-slate-200 bg-slate-100 cursor-not-allowed opacity-60' : ''}
          ${isDragActive && !disabled ? 'border-brand bg-blue-50' : 'border-slate-300 bg-white hover:border-brand hover:bg-slate-50'}`}
      >
        <input {...getInputProps()} />
        <UploadIcon className="mx-auto mb-3 text-brand" size={32} strokeWidth={1.5} />
        <div className="text-base font-semibold text-slate-900 mb-1">
          拖拽文件或文件夹到此处
        </div>
        <div className="text-xs text-slate-500 mb-4">
          支持 {allowedTypes.slice(0, 8).join(' / ')}{allowedTypes.length > 8 ? ' 等' : ''}
          , 单个文件 ≤ {maxSizeMb}MB
        </div>
        {!disabled && (
          <span className="inline-block px-4 py-2 bg-brand hover:bg-brand-dark text-white text-sm font-semibold rounded-md transition-colors shadow-sm">
            选择文件
          </span>
        )}
      </div>

      {!disabled && (
        <div className="mt-2 text-center">
          <label className="text-xs text-slate-500 cursor-pointer hover:text-brand hover:underline">
            或 选择整个文件夹
            <input
              type="file"
              multiple
              {...({ webkitdirectory: '', directory: '' } as any)}
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files || [])
                if (files.length) onFiles(files)
                e.currentTarget.value = ''
              }}
            />
          </label>
        </div>
      )}
    </div>
  )
}
