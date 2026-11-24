setlocal commentstring=;%s

let s:exe = get(g:, 'skillfmt_executable', 'skillfmt')
if executable(s:exe)
  let &l:formatprg = s:exe . ' format'
endif
unlet s:exe
