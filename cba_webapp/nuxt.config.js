const proxyConfig = () => {
  let proxyTarget = ''
  const ctxPath = process.env.CBA_APP_CONTEXT_PATH || '/'

  if (process.env.CBA_APP_DEPLOY === 'docker') {
    const dockerApiHost = process.env.CBA_APP_API_HOST
    const dockerApiPort = process.env.CBA_APP_API_PORT

    proxyTarget = 'http://' + dockerApiHost + ':' + dockerApiPort + '/'
  } else {
    proxyTarget = 'http://localhost:8081/'
  }

  // https://github.com/chimurai/http-proxy-middleware/blob/master/recipes/pathRewrite.md#custom-rewrite-function
  const apiCustomRewrite = (pth, req) => {
    const ctx = `${ctxPath}api/`
    return pth.replace(ctx, '/')
  }

  // https://github.com/chimurai/http-proxy-middleware#context-matching
  const apiCustomMatching = (pathname, req) => {
    const ctx = `${ctxPath}api/`
    return pathname.match(ctx)
  }

  // https://github.com/nuxt-community/proxy-module/issues/57
  return [
    [
      apiCustomMatching,
      {
        target: proxyTarget,
        pathRewrite: apiCustomRewrite,
      },
    ],
  ]
}

export default {
  // Global page headers (https://go.nuxtjs.dev/config-head)
  head: {
    title: 'CBA WebApp',
    meta: [
      {charset: 'utf-8'},
      {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1'
      },
      {
        hid: 'description',
        name: 'description',
        content: ''
      }
    ],
    link: [
      {
        rel: 'icon',
        type: 'image/x-icon',
        href: '/favicon.ico'
      }
    ]
  },

  // Global CSS (https://go.nuxtjs.dev/config-css)
  css: [],

  // Plugins to run before rendering page (https://go.nuxtjs.dev/config-plugins)
  plugins: [
    '@/plugins/generalApiClient.js',
    '@/plugins/datasetApiClient.js',
    '@/plugins/modelApiClient.js',
    '@/plugins/trainingApiClient.js',
    '@/plugins/predictionApiClient.js'
  ],

  // Auto import components (https://go.nuxtjs.dev/config-components)
  components: true,

  // Modules for dev and build (recommended) (https://go.nuxtjs.dev/config-modules)
  buildModules: [
    // https://go.nuxtjs.dev/eslint
    '@nuxtjs/eslint-module'
  ],

  // Modules (https://go.nuxtjs.dev/config-modules)
  modules: [
    // https://go.nuxtjs.dev/bootstrap
    'bootstrap-vue/nuxt',
    // https://go.nuxtjs.dev/axios
    '@nuxtjs/axios',
    '@nuxtjs/proxy',
    // https://www.npmjs.com/package/nuxt-highlightjs
    'nuxt-highlightjs'
  ],

  // https://github.com/nuxt-community/proxy-module#readme
  // necessary for CORS
  proxy: proxyConfig(),

  // Axios module configuration (https://go.nuxtjs.dev/config-axios)
  axios: {
    proxy: true
  },

  // https://bootstrap-vue.org/docs#icons
  bootstrapVue: {
    icons: true // Install the IconsPlugin (in addition to BootStrapVue plugin
  },

  // Build Configuration (https://go.nuxtjs.dev/config-build)
  build: {},

  router: {
    base: process.env.CBA_APP_CONTEXT_PATH
  },

  server: {
    port: 3000, // default: 3000
    host: '0.0.0.0', // default: localhost,
    timing: false
  },

  // https://nuxtjs.org/docs/2.x/directory-structure/nuxt-config#runtimeconfig
  publicRuntimeConfig: {
    ctxPath: process.env.CBA_APP_CONTEXT_PATH || '',
  },

}
