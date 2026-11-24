setlocal commentstring=;%s

let s:exe = get(g:, 'skillfmt_executable', 'skillfmt')
if executable(s:exe)
  call skillfmt#Refresh()
endif
unlet s:exe
