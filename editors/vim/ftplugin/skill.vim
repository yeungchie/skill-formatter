setlocal commentstring=;%s

if skfmt#Available()
  call skfmt#Setup()
endif
