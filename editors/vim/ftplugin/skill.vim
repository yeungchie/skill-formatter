setlocal commentstring=;%s

let s:exe = get(g:, 'skillfmt_executable', 'skill-formatter')
if executable(s:exe)
  call skillfmt#Setup()
endif
unlet s:exe
