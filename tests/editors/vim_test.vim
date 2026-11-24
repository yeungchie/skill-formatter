" Headless smoke test.  Run from the repository root:
"   vim -Nu NONE -es -S tests/editors/vim_test.vim

let s:root = fnamemodify(expand('<sfile>:p'), ':h:h:h')
let g:skillfmt_executable = ''
for s:candidate in [s:root . '/.venv/Scripts/skill-formatter.exe', s:root . '/.venv/bin/skill-formatter']
  if executable(s:candidate)
    let g:skillfmt_executable = s:candidate
    break
  endif
endfor
unlet s:candidate

if !executable(g:skillfmt_executable)
  cquit 2
endif

execute 'set runtimepath+=' . fnameescape(s:root . '/editors/vim')
runtime plugin/skillfmt.vim

function! s:Fail(message) abort
  echomsg 'FAIL: ' . a:message
  cquit 1
endfunction

let s:file = tempname() . '.il'
call writefile([
      \ 'procedure(foo(a "t")',
      \ 'a = 1',
      \ ')',
      \ ], s:file)
execute 'edit ' . fnameescape(s:file)

Skillfmt
let s:lines = getline(1, '$')
if s:lines != ['procedure(foo(a "t")', '    a = 1', ')']
  call s:Fail('whole buffer formatting: ' . string(s:lines))
endif

call setline(1, ['procedure(foo(a "t")', '    let((x)', '        x=1', '    )', ')'])
2,4SkillfmtRange
let s:lines = getline(1, '$')
if s:lines[1] != '    let((x)' || s:lines[2] != '        x=1' || s:lines[3] != '    )'
  call s:Fail('range formatting: ' . string(s:lines))
endif

let g:skillfmt_args = '--line-width 80'
SkillfmtRefresh
if &l:formatprg !~# '--line-width 80'
  call s:Fail('refresh did not apply g:skillfmt_args: ' . &l:formatprg)
endif

call delete(s:file)
qall!
