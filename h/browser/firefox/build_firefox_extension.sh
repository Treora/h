# Don't read this stuff, it may hurt your eyes!

echo
echo
echo "Attempting to build Firefox Extension.."
echo "Extension will be tied to URL: $1"
echo
echo

mkdir build
cd build

# Get the SDK
wget --no-clobber "https://ftp.mozilla.org/pub/mozilla.org/labs/jetpack/jetpack-sdk-latest.tar.gz"
tar -xf jetpack-sdk-latest.tar.gz
sdk_name=`find -regex "./addon-sdk-[0-9]+\.[0-9]+"`

# Clone the addon
git clone https://github.com/hypothesis/firefox-addon.git

old_url="https:\/\/hypothes\.is"
# Escape the given new url for sed
new_url=`sed -e "s/[\\/&]/\\\\\\\\&/g" <<< $1`

# Replace the URL in the addon's source code
sed -i "s/${old_url}/${new_url}/" firefox-addon/lib/main.js


# Activate SDK's virtual environment
cd $sdk_name
source bin/activate

# Finally, build the thing.
cd ../firefox-addon
cfx xpi

mv hypothesis.xpi ../..

echo "Done building the extension (hopefully)"
echo
