export interface Config {
  app?: {
    /**
     * The look of the portal for one organization. It is read from
     * branding/branding.yaml, so a client gets its own portal without
     * changing code. See branding/README.md.
     */
    branding?: {
      /**
       * Image in the sidebar when it is open, a file of the branding folder.
       * @visibility frontend
       */
      logo?: string;
      /**
       * Image in the sidebar when it is closed, a file of the branding folder.
       * @visibility frontend
       */
      logoIcon?: string;
      /**
       * Browser tab icon (.ico, .png or .svg), a file of the branding folder.
       * @visibility frontend
       */
      favicon?: string;
      /** The welcome card of the home page. */
      home?: {
        /** @visibility frontend */
        title?: string;
        /** @visibility frontend */
        subtitle?: string;
        /**
         * Markdown.
         * @visibility frontend
         */
        content?: string;
      };
      /** The page shown before signing in. */
      signIn?: {
        /** @visibility frontend */
        title?: string;
      };
    };
  };
}
