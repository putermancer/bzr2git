#!/usr/bin/env python

import os, shutil, subprocess, time
from optparse import OptionParser

USAGE = """%prog [options] name

Converts a bzr repository into a git repository with various options."""

def run(*cmds):
    output = []
    for cmd in cmds:
        try:
            p = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            stdout, stderr = p.communicate()
            if p.returncode is not 0:
                raise Exception(stderr)
            output.append(stdout.strip())
        except Exception, e:
            raise Exception("error executing the command: %s\n\n%s" % (cmd, e))
    return output[0] if len(output) == 1 else output

def Main():
    parser = OptionParser(usage = USAGE)
    parser.add_option("-F", "--no-git-flow", dest = "gitflow", action = "store_false", default = True, help = "do not prep the repository for git-flow (default: prep)")
    parser.add_option("-k", "--keep", dest = "keep", action = "store_true", default = False, help = "keep a copy of the original bzr repo on disk")
    parser.add_option("-r", "--repo", dest = "repo", type = "string", help = "url of the repository to convert; if not specified, assumes that 'name' is a local or checked out bzr repository")
    parser.add_option("-t", "--tree-only", dest = "tree", type = "string", help = "subdirectory to create as new project root; other history will be discarded")
    parser.add_option("-T", "--tree-exclude", dest = "tree_exclude", type = "string", help = "subdirectory to discarded, along with its history")
    parser.add_option("-c", "--cripple", dest = "cripple", action = "store_true", default = False, help = "cripple the BZR repo when done (remove all files, add a README saying it was migrated)")
    options, args = parser.parse_args()

    # raise errors on weird conditions
    if len(args) not in (1,2):
        parser.error("Incorrect number of arguments")
    if options.tree and options.tree_exclude:
        parser.error("tree and tree-exclude are mutually exclusive options")
    if (options.tree or options.tree_exclude) and options.cripple:
        parser.error("cripple and tree are (currently) mutually exclusive options")

    name = args.pop(0).rstrip("/")
    gitname = ("%s.git" % args.pop(0)).replace(".git.git", ".git") if len(args) else "%s.git" % name
    if not options.repo and not os.path.isdir(os.path.join(name, ".bzr")):
        parser.error("No bzr repo found at %s" % name)
    elif os.path.isdir(gitname):
        parser.error("%s already exists; have you migrated this repo already?" % gitname)
    elif options.repo and os.path.isdir(name):
        parser.error("%s already exists; are you sure you want to checkout another copy?" % name)

    gitpath = os.path.abspath(os.path.join(os.getcwd(), gitname))

    print "Migrating %s to git" % name

    # make a backup in case something goes wrong
    BACKUP_DIR = "%s.__backup__" % name
    if os.path.isdir(name):
        shutil.copytree(name, BACKUP_DIR, symlinks = True)

    cwd = os.getcwd()
    try:
        if options.repo:
            print " * Checking out repository at %s" % options.repo
            run("bzr checkout %s %s" % (options.repo, name))
        os.chdir(name)

        # things go south if the repo has no commit history
        if run("bzr revno") == "0":
            print " * bzr revno is 0; performing initial commit"
            run('bzr commit --unchanged -m "Initial commit"')

        # quick convert
        print " * Migrating commit history from bzr to git"
        run("git init", "bzr fast-export `pwd` | git fast-import")
        if options.cripple:
            print " * Crippling the BZR repo"
            for node in [n for n in os.listdir(".") if n != ".git" and n != ".bzr"]:
                if os.path.isfile(node):
                    os.remove(node)
                elif os.path.isdir(node):
                    shutil.rmtree(node)
            open("README", "wb").write("This repository has been migrated to Git.\nLook in the Git repo for the appropriate version of this project.")
            run("bzr add README")
            try:
                i = 5
                while i:
                    print "    Committing dead BZR repo to server in %s seconds... (ctrl-c to skip)" % i
                    time.sleep(1)
                    i -= 1
                print "   - Committing..."
                run('bzr commit -m "Crippled the repo; it has been migrated to git"')
            except KeyboardInterrupt:
                print "  - Skipped commit of dead BZR repo"

        run("rm -rf .bzr", "git reset --hard HEAD")
        ignore = None
        if os.path.exists(".bzrignore"):
            ignore = open(".bzrignore").read()
            run("git mv .bzrignore .gitignore", "git add .gitignore", 'git commit -m "Migrate .bzrignore to .gitignore"')

        MIGRATE_ALL = True
        if options.tree or options.tree_exclude:
            tree = options.tree if options.tree else options.tree_exclude
            if options.tree:
                if os.path.isdir(tree):
                    MIGRATE_ALL = False
                    # promote the tree and prune all history not pertinent to it
                    print " * Pruning out everything except the %s tree (this may take a while)" % tree
                    run("git filter-branch --subdirectory-filter %s HEAD -- --all" % tree, "git reset --hard")
                else:
                    print "   ! Specified tree not found; migrating the whole repo"
            else:
                MIGRATE_ALL = False
                # destroy the tree(s) and historical references
                print " * Destroying the specified tree(s) and all historical commit references (this may take a while)"
                run('git filter-branch --index-filter "git rm -r -f --cached --ignore-unmatch %s" --prune-empty HEAD' % tree, "git reset --hard")

        if MIGRATE_ALL:
            # create the shared bare repo
            print " * Creating a bare git clone at %s" % gitname
            run("git clone --bare %s %s" % (os.getcwd(), gitpath))
        else:
            if ignore:
                open(".gitignore", "wb").write(ignore)
                run("git add .gitignore", 'git commit -m "Migrate old .bzrignore to .gitignore"')
            # create the destination bare repo and push to it; doing this
            # will free up disk space used by commits we just ignored
            print " * Creating a bare git clone at %s" % gitname
            run("git init --bare %s" % gitpath, "git push %s HEAD" % gitpath)

        os.chdir(gitpath)
        # set up git-flow branches
        if options.gitflow:
            print " * Prepping branches for git-flow"
            run("git branch -m master develop", "git branch production")

        # pack the new repo
        print " * Aggressively packing the new repo"
        run("git gc --aggressive")

        # set up git-daemon and web ui hooks
        open("git-daemon-export-ok", "wb").write('')
        shutil.move(os.path.join("hooks", "post-update.sample"), os.path.join("hooks", "post-update"))

        # set some config options
        run("git config core.sharedrepository true")
        run("git config core.ignorecase false")
        run("git config receive.denyNonFastForwards true")

        # verify correct file permissions
        run("find objects -type d -exec chmod 02775 {} \;")

        # clean up
        print " * Cleaning up working directories"
        os.chdir(cwd)
        if os.path.isdir(name):
            shutil.rmtree(name)
        if os.path.isdir(BACKUP_DIR):
            if options.keep:
                shutil.move(BACKUP_DIR, name)
            else:
                shutil.rmtree(BACKUP_DIR)
        print "Success! Place the bare git repo in the desired location."
    except Exception, e:
        os.chdir(cwd)
        if os.path.isdir(name):
            shutil.rmtree(name)
        if os.path.isdir(BACKUP_DIR):
            shutil.move(BACKUP_DIR, name)
        print "\nError:", e

if __name__ == "__main__":
    Main()

