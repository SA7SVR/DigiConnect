<?php
// DigiConnect server config. Copy to config.php and edit.
return [
  'admin_user'  => 'admin',
  'admin_pass'  => 'CHANGE-THIS',   // the password for /digiconnect/admin/
  'demo_days'   => 7,               // default demo length for a new install
  'check_every' => 3600,            // app update-check interval in seconds (min 60)
  'gate'        => true             // true = enforce demo/licence; false = free for everyone
];
