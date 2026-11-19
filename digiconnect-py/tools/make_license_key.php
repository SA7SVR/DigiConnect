<?php
// DigiConnect — makes a NEW licence signing key pair (Ed25519). Only needed if license-key.php is lost everywhere (server AND data/license-key.bak.php AND your own copy).
// Usage:  php tools/make_license_key.php  [output file, default: license-key.php in the current folder]
// It never overwrites an existing file. It prints the PUBLIC key: put it into app/license.py (PUBKEYS list) and release a new program version.
// Programs that were released with the OLD public key keep working only if the old key is still in their list, so ADD the new key, do not replace the old one.
if (!function_exists('sodium_crypto_sign_keypair')) { fwrite(STDERR, "PHP sodium extension is missing\n"); exit(1); }
$out = $argv[1] ?? 'license-key.php';
if (file_exists($out)) { fwrite(STDERR, "$out exists - not overwritten\n"); exit(1); }
$kp = sodium_crypto_sign_keypair();
$sec = base64_encode(sodium_crypto_sign_secretkey($kp)); $pub = base64_encode(sodium_crypto_sign_publickey($kp));
file_put_contents($out, "<?php\n// DigiConnect licence signing key - SECRET. Never put this file in a public place (not in the package, not in git).\ndefine('LIC_SECRET', '$sec');\ndefine('LIC_PUBLIC', '$pub');\n");
@chmod($out, 0600);
echo "written: $out\nPUBLIC key (for app/license.py PUBKEYS): $pub\n";
