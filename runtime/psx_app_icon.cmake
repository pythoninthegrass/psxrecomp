# Which .ico a runtime target embeds and stages as its window icon.
#
# Kept in its own file, with no project-mode commands, so that
# runtime/tests/test_app_icon_resolve.py can drive the real resolution through
# `cmake -P` without configuring a whole runtime.
#
# psx_resolve_app_icon(<out_var> <explicit> <game_dir> <framework_root>)
#
# Order: an explicit APP_ICON, then <game_dir>/assets/psxrecomp.ico, then the
# framework default <framework_root>/assets/psxrecomp.ico. The literal NONE
# declares that the target ships no icon and skips the fallbacks, leaving the
# PE without an embedded icon and the window on the toolkit default.
function(psx_resolve_app_icon out_var explicit game_dir framework_root)
    if(explicit STREQUAL "NONE")
        set(${out_var} "" PARENT_SCOPE)
    elseif(explicit)
        set(${out_var} "${explicit}" PARENT_SCOPE)
    elseif(EXISTS "${game_dir}/assets/psxrecomp.ico")
        set(${out_var} "${game_dir}/assets/psxrecomp.ico" PARENT_SCOPE)
    elseif(EXISTS "${framework_root}/assets/psxrecomp.ico")
        set(${out_var} "${framework_root}/assets/psxrecomp.ico" PARENT_SCOPE)
    else()
        set(${out_var} "" PARENT_SCOPE)
    endif()
endfunction()
