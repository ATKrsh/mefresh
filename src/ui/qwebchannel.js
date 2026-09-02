"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10,
};

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The transport object doesn't implement a send function.");
        return;
    }

    var channel = this;
    this.transport = transport;
    this.send = function(data) {
        if (typeof data !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    };

    this.transport.onmessage = function(message) {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("invalid message received:", message.data);
                break;
        }
    };

    this.execCallbacks = {};
    this.execId = 0;
    this.exec = function(data, callback) {
        if (!callback) {
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_VALUE) {
            channel.execId = 0;
        }
        data.id = ++channel.execId;
        channel.execCallbacks[data.id] = callback;
        channel.send(data);
    };

    this.objects = {};
    this.handleSignal = function(message) {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Unhandled signal: " + message.object + "::" + message.signal);
        }
    };

    this.handleResponse = function(message) {
        if (!message.hasOwnProperty("id")) {
            console.error("Invalid response message received: ", JSON.stringify(message));
            return;
        }
        var callback = channel.execCallbacks[message.id];
        if (callback) {
            delete channel.execCallbacks[message.id];
            var resData = (typeof message.data !== "undefined") ? message.data : message.response;
            callback(resData);
        }
    };

    this.handlePropertyUpdate = function(message) {
        for (var i in message.data) {
            var data = message.data[i];
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("Unhandled property update: " + data.object + "::" + data.signal);
            }
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    };

    this.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (var objectName in data) {
            new QObject(objectName, data[objectName], channel);
        }
        for (var name in channel.objects) {
            channel.objects[name].unwrapProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    });
};

function QObject(name, data, webChannel) {
    this.__id__ = name;
    webChannel.objects[name] = this;
    var self = this;
    this.signals = {};

    this.unwrapProperties = function() {
        if (data.properties) {
            for (var propName in data.properties) {
                var prop = data.properties[propName];
                if (prop && prop.type === "QObject") {
                    this[propName] = webChannel.objects[prop.id];
                }
            }
        }
    };

    this.propertyUpdate = function(signals, propertyMap) {
        for (var propertyIndex in propertyMap) {
            var propertyValue = propertyMap[propertyIndex];
            data.properties[propertyIndex] = propertyValue;
            var propertyName = data.propertyNames[propertyIndex];
            this[propertyName] = propertyValue;
        }
        for (var signalIndex in signals) {
            var signalArgs = signals[signalIndex];
            this.signalEmitted(signalIndex, signalArgs);
        }
    };

    this.signalEmitted = function(signalIndex, signalArgs) {
        var sigObj = this.signals[signalIndex];
        if (sigObj) {
            sigObj.apply(this, signalArgs);
        }
    };

    function createMethod(methodName) {
        return function() {
            var args = [];
            var callback = null;
            for (var i = 0; i < arguments.length; ++i) {
                var arg = arguments[i];
                if (typeof arg === "function") {
                    callback = arg;
                } else if (arg instanceof QObject) {
                    args.push({
                        type: "QObject",
                        id: arg.__id__
                    });
                } else {
                    args.push(arg);
                }
            }
            webChannel.exec({
                type: QWebChannelMessageTypes.invokeMethod,
                object: self.__id__,
                method: methodName,
                args: args
            }, function(response) {
                if (response && response.type === "QObject") {
                    response = webChannel.objects[response.id];
                }
                if (callback) {
                    callback(response);
                }
            });
        };
    }

    function createSignal(signalIndex, signalName) {
        var signal = function() {
            var subscribers = signal.subscribers;
            for (var i = 0; i < subscribers.length; ++i) {
                subscribers[i].apply(this, arguments);
            }
        };
        signal.subscribers = [];
        signal.connect = function(callback) {
            if (typeof callback !== "function") {
                console.error("Bad callback given to connect to signal " + signalName);
                return;
            }
            if (signal.subscribers.indexOf(callback) === -1) {
                signal.subscribers.push(callback);
                if (signal.subscribers.length === 1) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.connectToSignal,
                        object: self.__id__,
                        signal: signalIndex
                    });
                }
            }
        };
        signal.disconnect = function(callback) {
            if (typeof callback !== "function") {
                console.error("Bad callback given to disconnect from signal " + signalName);
                return;
            }
            var idx = signal.subscribers.indexOf(callback);
            if (idx !== -1) {
                signal.subscribers.splice(idx, 1);
                if (signal.subscribers.length === 0) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.disconnectFromSignal,
                        object: self.__id__,
                        signal: signalIndex
                    });
                }
            }
        };
        return signal;
    }

    if (data.methods) {
        for (var i = 0; i < data.methods.length; ++i) {
            var methodDef = data.methods[i];
            var methodName = Array.isArray(methodDef) ? methodDef[0] : methodDef;
            this[methodName] = createMethod(methodName);
        }
    }

    if (data.signals) {
        for (var j = 0; j < data.signals.length; ++j) {
            var sigDef = data.signals[j];
            var sigName = Array.isArray(sigDef) ? sigDef[0] : sigDef;
            var sigIndex = Array.isArray(sigDef) ? sigDef[1] : j;
            if (!this.signals[sigIndex]) {
                this.signals[sigIndex] = createSignal(sigIndex, sigName);
            }
            this[sigName] = this.signals[sigIndex];
            this.signals[sigName] = this.signals[sigIndex];
        }
    }
}
