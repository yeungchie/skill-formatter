setlocal commentstring=;%s

let s:exe = get(g:, 'skillfmt_executable', 'skillfmt')
if executable(s:exe)
  call skillfmt#Setup()
endif
unlet s:exe
