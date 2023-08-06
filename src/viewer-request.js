function handler(event) {
    var request = event.request;
    var routes = request.uri.split("/");
    // assume uri to be like /**/* or /**/*/ that require modification
    // modify uri by appending .html so that the right object can be found in s3 

    if (routes[routes.length - 1] === "") {
        routes.pop();
    }

    if (routes.length > 0) {

        var lastRoute = routes[routes.length - 1];

        if (lastRoute !== "" && !routes[routes.length - 1].includes(".")) {
            routes[routes.length - 1] += ".html";
        }

        var newUri = routes.join("/");

        if (!newUri.startsWith("/")) {
            newUri = "/" + newUri;
        }

        request.uri = newUri;

        return request;
    } else {
        return request;
    }
}