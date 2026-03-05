import { useState, useEffect, useRef, type KeyboardEvent } from 'react';

interface ConfirmProps {
  open: boolean;
  title?: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', danger = true, onConfirm, onCancel }: ConfirmProps) {
  useEffect(() => {
    if (!open) return;
    const h = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
      if (e.key === 'Enter') onConfirm();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onConfirm, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div className="bg-bg1 border border-border rounded-sm p-5 w-[360px] shadow-xl" onClick={e => e.stopPropagation()}>
        {title && <div className="text-xs font-bold text-text tracking-wider mb-3">{title}</div>}
        <div className="text-xs text-text2 mb-5 leading-relaxed">{message}</div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-1.5 text-[11px] text-text3 border border-border rounded-sm hover:text-text hover:border-border2 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-1.5 text-[11px] font-bold rounded-sm transition-colors ${
              danger
                ? 'bg-red/20 text-red border border-red/30 hover:bg-red/30'
                : 'bg-amber text-bg hover:bg-amber2'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

interface PromptProps {
  open: boolean;
  title?: string;
  placeholder?: string;
  defaultValue?: string;
  onSubmit: (value: string) => void;
  onCancel: () => void;
}

export function PromptDialog({ open, title, placeholder, defaultValue = '', onSubmit, onCancel }: PromptProps) {
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setValue(defaultValue);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open, defaultValue]);

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && value.trim()) onSubmit(value.trim());
    if (e.key === 'Escape') onCancel();
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div className="bg-bg1 border border-border rounded-sm p-5 w-[360px] shadow-xl" onClick={e => e.stopPropagation()}>
        {title && <div className="text-xs font-bold text-text tracking-wider mb-3">{title}</div>}
        <input
          ref={inputRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full bg-bg2 border border-border rounded-sm px-3 py-2 text-text text-xs font-mono
            placeholder:text-text3 outline-none focus:border-border2 mb-4"
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-1.5 text-[11px] text-text3 border border-border rounded-sm hover:text-text hover:border-border2 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => value.trim() && onSubmit(value.trim())}
            disabled={!value.trim()}
            className="px-4 py-1.5 text-[11px] font-bold bg-amber text-bg rounded-sm hover:bg-amber2 transition-colors disabled:opacity-30"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
