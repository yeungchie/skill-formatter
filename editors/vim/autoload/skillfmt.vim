" Autoload functions for skillfmt.vim.  Vim 7.4 compatible.

if v:version < 704
  finish
endif

let s:save_cpo = &cpo
set cpo&vim

function! s:Executable() abort
  return get(g:, 'skillfmt_executable', 'skillfmt')
endfunction

function! s:ShowError(file) abort
  let l:lines = filereadable(a:file) ? readfile(a:file) : ['skillfmt failed']
  echohl ErrorMsg
  for l:line in l:lines
    echomsg l:line
  endfor
  echohl None
endfunction

function! s:Replace(lines) abort
  if a:lines == getline(1, '$')
    return
  endif
  let l:view = winsaveview()
  silent %delete _
  if !empty(a:lines)
    silent! undojoin
    call append(0, a:lines)
    silent! undojoin
    silent $delete _
  endif
  call winrestview(l:view)
endfunction

function! skillfmt#Format(all, first, last) abort
  let l:exe = s:Executable()
  if !executable(l:exe)
    echohl ErrorMsg
    echomsg 'skillfmt: executable not found: ' . l:exe
    echohl None
    return
  endif

  let l:in_file = tempname()
  let l:out_file = tempname()
  let l:err_file = tempname()
  try
    call writefile(getline(1, '$'), l:in_file)
    let l:cmd = shellescape(l:exe)
    let l:extra = get(g:, 'skillfmt_args', '')
    if !empty(l:extra)
      let l:cmd .= ' ' . l:extra
    endif
    let l:path = expand('%:p')
    if !empty(l:path)
      let l:cmd .= ' --stdin-path ' . shellescape(l:path)
    endif
    if !a:all
      let l:cmd .= ' --lines ' . a:first . ':' . a:last
    endif
    let l:cmd .= ' < ' . shellescape(l:in_file)
    let l:cmd .= ' > ' . shellescape(l:out_file)
    let l:cmd .= ' 2> ' . shellescape(l:err_file)
    silent call system(l:cmd)
    if v:shell_error
      call s:ShowError(l:err_file)
      return
    endif
    if !filereadable(l:out_file)
      echohl ErrorMsg
      echomsg 'skillfmt: no output produced'
      echohl None
      return
    endif
    call s:Replace(readfile(l:out_file))
  finally
    for l:file in [l:in_file, l:out_file, l:err_file]
      if filereadable(l:file)
        call delete(l:file)
      endif
    endfor
  endtry
endfunction

function! skillfmt#FormatAll() abort
  call skillfmt#Format(1, 1, line('$'))
endfunction

function! skillfmt#FormatRange(first, last) abort
  call skillfmt#Format(0, a:first, a:last)
endfunction

let &cpo = s:save_cpo
unlet s:save_cpo
