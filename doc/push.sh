set -e
# Make fresh clone
git clone ../ temp_clone
pushd temp_clone/doc/

# Build new docs
make html

# Copy relevant files to doc_temp
cd ..
mv doc/html doc_temp

# Remove previous files and branch
git checkout --orphan gh-pages
git rm -rf .

# Ensure that .nojekyll is set for github to ignore _'d dirs
touch .nojekyll
git add .nojekyll

# Update git
mv ./doc_temp/* .
git add *.html
git add *.js
git add *.inv
git add ./_*
git commit -m "Docs Commit"
git push -f origin gh-pages

# Return to the base doc directory and remove temp clone
popd
rm -rf temp_clone