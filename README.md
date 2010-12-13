About
-----
bzr2git.py is a tool I originally created to simply migrate BZR repositories
to Git.  As I have encountered additional obstacles, I have modified this
script to suit my needs.

While it is by no means perfect, it has several nice options:

* works with either local or remote bzr repos (as long as you can check it out)
* maintain bzr commit history (tag preservation is untested)
* prep a repository for the [git-flow](http://nvie.com/posts/a-successful-git-branching-model/) branching model
* migrate a single sub-directory (with only its history) to its own git repo
  * useful for converting part of a project for use as submodules
* ignore one or more directories (or files) and their history
  * useful when you have converted parts of a project for use as submodules :)
* cripple the bzr repository
  * delete all files, create a README saying "migrated to git," push to bzr repo


License
-------
This software is distributed under the MIT license.
