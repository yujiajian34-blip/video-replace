(function (root, factory) {
    const api = factory();

    if (typeof module !== "undefined" && module.exports) {
        module.exports = api;
    }

    if (root) {
        root.resolveApiBase = api.resolveApiBase;
    }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    function resolveApiBase(locationLike) {
        if (locationLike && locationLike.protocol === "file:") {
            return "http://127.0.0.1:5001";
        }

        if (locationLike && locationLike.origin && locationLike.origin !== "null") {
            return locationLike.origin;
        }

        return "http://127.0.0.1:5001";
    }

    return { resolveApiBase };
});
