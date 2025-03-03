# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## v0.2.0 - 2025-03-03
* Large refactor with lots of features added:
** Added `render` command to allow renders of prepared markdown letters
** Added `output-directory` config option to specify where letters should be saved
** Added an internal backup directory to store intermediate versions (and prevent accidental deletes!)
** Added ability to inspect config even if it is invalid
** Added ability for user to provide their own prompts instead of the builtins
** Added an option for the user to provide an editor command
** Improved LLM prompts for `generate` command

## v0.1.2 - 2025-02-28
* Fixed generate...not sure how it got broken

## v0.1.1 - 2025-02-28
* Fixed README badges

## v0.1.0 - 2025-02-28
* Initial release
