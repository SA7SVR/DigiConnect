<?php
/* DigiConnect host-file sources. Each mode's full server list is mirrored from the
   canonical upstream used by every DV client, then your own HELLAS Zone reflectors
   (hosts/custom/<file>) are prepended so they appear first. Edit this to add mirrors. */
return [
  // file served to the app   => [ upstream URLs tried in order ]
  'DMRHosts.txt'  => ['http://www.dudetronics.com/ar-dns/DMRHosts.txt', 'https://hostfiles.w0chp.net/DMR_Hosts.txt', 'https://www.pistar.uk/downloads/DMR_Hosts.txt'],
  'YSFHosts.txt'  => ['http://www.dudetronics.com/ar-dns/YSFHosts.txt', 'https://register.ysfreflector.de/export.php', 'https://hostfiles.w0chp.net/YSFHosts.txt', 'https://www.pistar.uk/downloads/YSFHosts.txt'],
  'FCSHosts.txt'  => ['http://www.dudetronics.com/ar-dns/FCSHosts.txt'],
  'P25Hosts.txt'  => ['http://www.dudetronics.com/ar-dns/P25Hosts.txt', 'https://hostfiles.w0chp.net/P25Hosts.txt', 'https://www.pistar.uk/downloads/P25Hosts.txt'],
  'NXDNHosts.txt' => ['http://www.dudetronics.com/ar-dns/NXDNHosts.txt', 'https://hostfiles.w0chp.net/NXDNHosts.txt', 'https://www.pistar.uk/downloads/NXDNHosts.txt'],
  'M17Hosts-full.csv' => ['http://www.dudetronics.com/ar-dns/M17Hosts-full.csv', 'https://hostfiles.w0chp.net/M17_Hosts.txt', 'https://www.pistar.uk/downloads/M17_Hosts.txt'],
  'ASLHosts.txt'  => ['http://www.dudetronics.com/ar-dns/ASLHosts.txt', 'https://hostfiles.w0chp.net/ASLHosts.txt'],
  'dplus.txt'     => ['http://www.dudetronics.com/ar-dns/dplus.txt', 'https://hostfiles.w0chp.net/DPlus_Hosts.txt', 'https://www.pistar.uk/downloads/DPlus_Hosts.txt'],   // D-Star REF
  'dextra.txt'    => ['http://www.dudetronics.com/ar-dns/dextra.txt', 'https://hostfiles.w0chp.net/DExtra_Hosts.txt', 'https://www.pistar.uk/downloads/DExtra_Hosts.txt'],  // D-Star XRF
  'dcs.txt'       => ['http://www.dudetronics.com/ar-dns/dcs.txt', 'https://hostfiles.w0chp.net/DCS_Hosts.txt', 'https://www.pistar.uk/downloads/DCS_Hosts.txt'],     // D-Star DCS
  'DMRIDs.dat'    => ['https://radioid.net/static/user.csv', 'http://www.dudetronics.com/ar-dns/DMRIDs.dat'],
];
