const createPayloadBuilders = {};

function registerCreateBuilder(type, fn) {
  createPayloadBuilders[type] = fn;
}

