/* Fixture only — deliberately unsafe Workbox-like SW for red-path checks.
 * Must NEVER be copied into dist/ or served in production.
 */
import {precaching, routing, strategies} from 'workbox-placeholder';
precaching.precacheAndRoute([
  {url: 'index.html', revision: 'fixture-unsafe'},
  {url: 'assets/app.js', revision: 'fixture'},
]);
routing.registerRoute(
  new routing.NavigationRoute(strategies.createHandlerBoundToURL('index.html')),
);
