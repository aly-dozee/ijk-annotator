window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        close_window: function(n_clicks) {
            setTimeout(() => {
                window.open('', '_self').close();
            }, 50);
            return null;
        }
    }
});
