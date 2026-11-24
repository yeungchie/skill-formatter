" Autoload functions for skfmt.vim.  Vim 7.4 compatible.

if v:version < 704
  finish
endif

let s:save_cpo = &cpo
set cpo&vim

let s:tool = 'skfmt'
let s:min_version = '0.1.0'
let s:version_ok = -1
let s:version_exe = ''

function! s:CommandParts() abort
  let l:configured = get(g:, 'skfmt_executable', '')
  if !empty(l:configured) && l:configured !=# s:tool
    return [l:configured, '', 'configured']
  endif
  if executable(s:tool)
    return [s:tool, '', 'local']
  endif
  if executable('uvx')
    return ['uvx', s:tool, 'uvx']
  endif
  if executable('uv')
    return ['uv', 'tool run ' . s:tool, 'uv']
  endif
  return ['', '', '']
endfunction

function! s:JoinCommand(exe, prefix) abort
  if empty(a:exe)
    return ''
  endif
  let l:cmd = shellescape(a:exe)
  if !empty(a:prefix)
    let l:cmd .= ' ' . a:prefix
  endif
  return l:cmd
endfunction

function! s:Command() abort
  let l:parts = s:CommandParts()
  return s:JoinCommand(l:parts[0], l:parts[1])
endfunction

function! skfmt#Available() abort
  return !empty(s:Command())
endfunction

function! skfmt#Command() abort
  return s:Command()
endfunction

function! s:ShowMessage(message) abort
  echohl ErrorMsg
  echomsg a:message
  echohl None
endfunction

function! s:VersionAtLeast(found, required) abort
  let l:found = split(a:found, '\.')
  let l:required = split(a:required, '\.')
  if len(l:found) < 3 || len(l:required) < 3
    return 0
  endif
  let l:index = 0
  while l:index < 3
    let l:left = str2nr(l:found[l:index])
    let l:right = str2nr(l:required[l:index])
    if l:left > l:right
      return 1
    elseif l:left < l:right
      return 0
    endif
    let l:index = l:index + 1
  endwhile
  return 1
endfunction

function! s:ReadVersion() abort
  let l:cmd = s:Command()
  if empty(l:cmd)
    return ''
  endif
  let l:output = system(l:cmd . ' --version')
  if v:shell_error
    return ''
  endif
  return matchstr(l:output, '\d\+\.\d\+\.\d\+')
endfunction

function! skfmt#VersionOk() abort
  let l:parts = s:CommandParts()
  let l:command = s:JoinCommand(l:parts[0], l:parts[1])
  if s:version_exe !=# l:command
    let s:version_ok = -1
    let s:version_exe = l:command
  endif
  if s:version_ok >= 0
    return s:version_ok
  endif
  if empty(l:command)
    let s:version_ok = 0
    call s:ShowMessage(s:tool . ': not found; install skfmt or make uvx available')
    return 0
  endif
  let l:found = s:ReadVersion()
  if empty(l:found)
    let s:version_ok = 0
    if l:parts[2] ==# 'uvx' || l:parts[2] ==# 'uv'
      call s:ShowMessage(
            \ s:tool . ': uvx could not run skfmt; install skfmt locally or ensure PyPI is reachable')
    else
      call s:ShowMessage(s:tool . ': cannot determine version; install or update the executable')
    endif
    return 0
  endif
  if !s:VersionAtLeast(l:found, s:min_version)
    let s:version_ok = 0
    call s:ShowMessage(
          \ s:tool . ' ' . l:found . ' is too old; requires >= ' . s:min_version
          \ . ' (upgrade, then :SkfmtRefresh)')
    return 0
  endif
  let s:version_ok = 1
  return 1
endfunction

function! skfmt#Version() abort
  let l:parts = s:CommandParts()
  let l:command = s:JoinCommand(l:parts[0], l:parts[1])
  if empty(l:command)
    echomsg s:tool . ': not found; install skfmt or make uvx available'
    return
  endif
  let l:found = s:ReadVersion()
  if empty(l:found)
    echomsg s:tool . ': version unknown via ' . l:command
  else
    echomsg s:tool . ' ' . l:found . ' via ' . l:command
          \ . ' (' . l:parts[2] . '; required >= ' . s:min_version . ')'
  endif
endfunction

function! skfmt#FormatPrg() abort
  let l:cmd = s:Command()
  if empty(l:cmd)
    return ''
  endif
  let l:cmd .= ' format'
  let l:extra = get(g:, 'skfmt_args', '')
  if !empty(l:extra)
    let l:cmd .= ' ' . l:extra
  endif
  return l:cmd
endfunction

function! skfmt#Refresh() abort
  let s:version_ok = -1
  call skfmt#Setup()
endfunction

function! skfmt#Setup() abort
  if skfmt#VersionOk()
    let &l:formatprg = skfmt#FormatPrg()
  else
    let &l:formatprg = ''
  endif
endfunction

function! s:ShowError(file) abort
  let l:lines = filereadable(a:file) ? readfile(a:file) : [s:tool . ' failed']
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

function! skfmt#Format(all, first, last) abort
  let l:parts = s:CommandParts()
  let l:command = s:JoinCommand(l:parts[0], l:parts[1])
  if empty(l:command)
    echohl ErrorMsg
    echomsg s:tool . ': not found; install skfmt or make uvx available'
    echohl None
    return
  endif
  if !skfmt#VersionOk()
    return
  endif

  let l:in_file = tempname()
  let l:out_file = tempname()
  let l:err_file = tempname()
  try
    call writefile(getline(1, '$'), l:in_file)
    let l:cmd = l:command . ' format'
    let l:extra = get(g:, 'skfmt_args', '')
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
      echomsg s:tool . ': no output produced'
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

function! skfmt#FormatAll() abort
  call skfmt#Format(1, 1, line('$'))
endfunction

function! skfmt#FormatRange(first, last) abort
  call skfmt#Format(0, a:first, a:last)
endfunction

let &cpo = s:save_cpo
unlet s:save_cpo
