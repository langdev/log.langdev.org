function ChatSession(options) {
    this.options = options;
    this.from = options.from || 0;
    this.onUpdate = options.onUpdate || function(){};
}

ChatSession.prototype = {
    start: function() {
        this.socket = io.connect(this.options.url);
        var self = this;
        this.socket.on('update', function() {
            self.update(self.onUpdate);
        });
    },

    send: function(msg) {
        this.socket.emit('msg', {
            nick: this.options.nickname,
            channel: this.options.channel,
            msg: msg
        });
    },
    
    update: function(next) {
        var self = this;
        $.getJSON('?from=' + this.from, function(data) {
            if (!data.html) return;
            self.from = data.last_no + 1;
            if (next) next.call(self, data.html);
        });
    }
};

function LogView(el) {
    this.el = el;
}

LogView.prototype = {
    append: function(data) {
        this.el.append(data);
        apply_noreferrer(this.el);
    },

    scrollToBottom: function() {
        $(window).scrollTop($(document).height() + 100000);
    },

    shouldScrollToBottom: function() {
        var $doc = $(document),
            $window = $(window);
        return $doc.height() <= $window.scrollTop() + $window.height() + 20;
    }
};

function ChatController(options) {
    this.options = options;
    this.session = options.session;
    this.session.onUpdate = $.proxy(this.onUpdate, this);

    var self = this;
    this.options.startChatView.on('click', function() {
        self.startChat();
        return false;
    });
    this.options.inputFormView.on('submit', function() {
        self.sendMessage();
        return false;
    });
}

ChatController.prototype = {
    startChat: function() {
        this.options.startChatView.slideUp();
        this.options.inputFormView.slideDown();
        var self = this;

        this.normalTitle = document.title;
        observeWindowVisibility(function(visible) {
            self.setWindowVisible(visible);
        });

        this.session.update(function(data) {
            self.appendLog(data);
            self.options.logView.scrollToBottom();
        });
        this.session.start();
    },

    onUpdate: function(data) {
        var willScroll = this.options.logView.shouldScrollToBottom();
        this.appendLog(data);
        if (willScroll)
            this.options.logView.scrollToBottom();
        if (!this._windowVisible)
            this.notifyPendingLog();
    },

    appendLog: function(data) {
        this.options.logView.append(data);
    },
    
    sendMessage: function() {
        var msg = this.options.inputView.val();
        if (msg) {
            this.session.send(msg);
            this.options.inputView.val('');
        }
    },

    setWindowVisible: function(visible) {
        if (!this._windowVisible && visible) {
            // Become visible
            document.title = this.normalTitle;
        }
        this._windowVisible = visible;
    },

    notifyPendingLog: function() {
        document.title = '+ ' + this.normalTitle;
    }
};

(function(exports) {
    var hidden, visibilityChange;
    if (typeof document.hidden !== "undefined") {
        hidden = "hidden";
        visibilityChange = "visibilitychange";
    } else if (typeof document.mozHidden !== "undefined") {
        hidden = "mozHidden";
        visibilityChange = "mozvisibilitychange";
    } else if (typeof document.msHidden !== "undefined") {
        hidden = "msHidden";
        visibilityChange = "msvisibilitychange";
    } else if (typeof document.webkitHidden !== "undefined") {
        hidden = "webkitHidden";
        visibilityChange = "webkitvisibilitychange";
    }

    exports.isWindowVisible = function() {
        return !document[hidden];
    };

    exports.observeWindowVisibility = function(callback) {
        if (typeof document.addEventListener !== "undefined" &&
            typeof hidden !== "undefined") {
            callback(exports.isWindowVisible());
            document.addEventListener(visibilityChange, function() {
                callback(exports.isWindowVisible());
            }, false);
        }
    };
})(window);
