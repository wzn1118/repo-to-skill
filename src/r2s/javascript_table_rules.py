from __future__ import annotations

TABLE_NORMALIZER = '''function normalize(__settings) {
 const __options = [];
 for (const [name, __original] of Object.entries(__settings)) {
  const __option = {name, ...__original};
  if (Array.isArray(__option.default)) { __option.default = __option.default.at(-1).value; }
  __options.push(__option);
 }
 return __options;
}'''

DETAIL_NORMALIZER = '''function normalize(__option) {
 return {
  category: __categories.CATEGORY_OTHER,
  ...__option,
  name: __option.cliName ?? __dashify(__option.name),
  choices: __option.choices?.map((__choice) => {
   const __next = {description: "", deprecated: false, ...(typeof __choice === "object" ? __choice : {value: __choice})};
   if (__next.value === true) { __next.value = ""; }
   return __next;
  }),
 };
}'''

API_CONVERTER = '''function convert(__option) {
 const __next = {
  ...__option,
  description: __option.cliDescription ?? __option.description,
  category: __option.cliCategory ?? __categories.CATEGORY_FORMAT,
  forwardToApi: __option.name,
 };
 if (__option.deprecated) {
  delete __next.forwardToApi;
  delete __next.description;
  delete __next.oppositeDescription;
  __next.deprecated = true;
 }
 return __normalize(__next);
}'''

CONTEXT_OPTIONS = '''function convert({options: __support, languages}) {
 const detailedOptions = [...__cli, ...__support.map((__option) => __convert(__option))];
 return {supportOptions: __support, languages, detailedOptions};
}'''

CONTEXT_PROVIDER = '''async function context(plugins) {
 const __support = await __getSupport({showDeprecated: true, plugins});
 return __convert(__support);
}'''

BASE_CONTEXT = '''function context() {
 const __support = __getSupport();
 return __convert(__support);
}'''

INITIAL_PARSER = '''function initial(__raw, __logger, __keys) {
 return __parse(__raw, __detailed, __logger, typeof __keys === "string" ? [__keys] : __keys);
}'''

PICK_FIELDS = '''function pick(__object, __keys) {
 const __entries = __keys.map((__key) => [__key, __object[__key]]);
 return Object.fromEntries(__entries);
}'''

SUPPORT_PROVIDER = '''function support({plugins = [], showDeprecated = false} = {}) {
 const languages = plugins.flatMap((__plugin) => __plugin.languages ?? []);
 const options = [];
 for (const __option of __normalize(Object.assign({}, ...plugins.map(({options}) => options), __core))) {
  if (!showDeprecated && __option.deprecated) { continue; }
  if (Array.isArray(__option.choices)) {
   if (!showDeprecated) { __option.choices = __option.choices.filter((__choice) => !__choice.deprecated); }
   if (__option.name === __literal_extended) {
    __option.choices = [...__option.choices, ...__collect(__option.choices, languages, plugins)];
   }
  }
  __option.pluginDefaults = Object.fromEntries(
   plugins.filter((__plugin) => __plugin.defaultOptions?.[__option.name] !== undefined)
    .map((__plugin) => [__plugin.name, __plugin.defaultOptions[__option.name]]),
  );
  options.push(__option);
 }
 return {languages, options};
}'''

COLLECT_CHOICES = '''function* collect(__choices, __languages, __plugins) {
 const __existing = new Set(__choices.map((__choice) => __choice.value));
 for (const __language of __languages) {
  if (__language.parsers) {
   for (const __name of __language.parsers) {
    if (!__existing.has(__name)) {
     __existing.add(__name);
     const __plugin = __plugins.find((__item) => __item.parsers && Object.hasOwn(__item.parsers, __name));
     let __description = __language.name;
     if (__plugin?.name) {__description += ` (plugin: ${__plugin.name})`;}
     yield {value: __name, description: __description};
    }
   }
  }
 }
}'''

PLUGIN_WRAPPER = '''function wrap(__function, __position = 1) {
 return async (...__args) => {
  const __options = __args[__position] ?? {};
  const {plugins = []} = __options;
  __args[__position] = {
   ...__options,
   plugins: (await Promise.all([__builtin(), __load(plugins)])).flat(),
  };
  return __function(...__args);
 };
}'''

MINIMIST_OPTIONS = '''function options(__detailed) {
 const __boolean = [];
 const __strings = ["_"];
 const __defaults = {};
 for (const __option of __detailed) {
  const {name, alias, type} = __option;
  const __names = type === "boolean" ? __boolean : __strings;
  __names.push(name);
  if (alias) { __names.push(alias); }
  if (!__option.deprecated && (!__option.forwardToApi || name === __literal_special) && __option.default !== undefined) {
   __defaults[__option.name] = __option.default;
  }
 }
 return {alias: {}, boolean: __boolean, string: __strings, default: __defaults};
}'''

MINIMIST_WRAPPER = '''function parse(__args, __options) {
 const __boolean = __options.boolean ?? [];
 const __defaults = __options.default ?? {};
 const __absent = __boolean.filter((__key) => !(__key in __defaults));
 const __next = {...__defaults, ...Object.fromEntries(__absent.map((__key) => [__key, __placeholder]))};
 const __parsed = __minimist(__args, {...__options, default: __next});
 return Object.fromEntries(Object.entries(__parsed).filter(([, __value]) => __value !== __placeholder));
}'''

ARGUMENT_PARSER = '''function parse(__raw, __detailed, logger, __keys) {
 const __options = __create(__detailed);
 let __argv = __minimist(__raw, __options);
 if (__keys) {
  __detailed = __detailed.filter((__option) => __keys.includes(__option.name));
  __argv = __pick(__argv, __keys);
 }
 const __normalized = __normalize(__argv, __detailed, {logger});
 return {
  ...Object.fromEntries(Object.entries(__normalized).map(([__key, __value]) => {
   const __option = __detailed.find(({name}) => name === __key) || {};
   return [__option.forwardToApi || __camel(__key), __value];
  })),
  _: __normalized._,
  get __rawProperty() {return __argv;},
 };
}'''

CONTEXT_INIT = '''async function init() {
 const {rawArguments, logger} = this;
 const {plugins} = __initial(rawArguments, logger, ["plugin"]);
 await this.__push(plugins);
 const __argv = __parse(rawArguments, this.detailedOptions, logger);
 this.argv = __argv;
 this.__positional = __argv._;
}'''

CONTEXT_PUSH = '''async function push(plugins) {
 const __options = await __provider(plugins);
 this.__stack.push(__options);
 Object.assign(this, __options);
}'''

CLI_NORMALIZER = '''function normalize(__options, __infos, __opts) {
 return __normalize(__options, __infos, {...__opts, isCLI: true, FlagSchema, descriptor});
}'''

SCHEMA_LIST = '''function schemas(__infos, {isCLI, FlagSchema}) {
 const __schemas = [];
 if (isCLI) {__schemas.push(__library.AnySchema.create({name: "_"}));}
 for (const __info of __infos) {
  __schemas.push(__convert(__info, {isCLI, optionInfos: __infos, FlagSchema}));
  if (__info.alias && isCLI) {
   __schemas.push(__library.AliasSchema.create({name: __info.alias, sourceName: __info.name}));
  }
 }
 return __schemas;
}'''

SCHEMA_FACTORY = '''function schema(__info, {isCLI, optionInfos, FlagSchema}) {
 const {name} = __info;
 const __parameters = {name};
 let __constructor;
 const __handlers = {};
 switch (__info.type) {
  case "int":
   __constructor = __library.IntegerSchema;
   if (isCLI) {__parameters.preprocess = Number;}
   break;
  case "string": __constructor = __library.StringSchema; break;
  case "choice":
   __constructor = __library.ChoiceSchema;
   __parameters.choices = __info.choices.map((__choice) => __choice?.redirect
    ? {...__choice, redirect: {to: {key: __info.name, value: __choice.redirect}}} : __choice);
   break;
  case "boolean": __constructor = __library.BooleanSchema; break;
  case "flag":
   __constructor = FlagSchema;
   __parameters.flags = optionInfos.flatMap((__option) => [__option.alias, __option.description && __option.name, __option.oppositeDescription && `no-${__option.name}`].filter(Boolean));
   break;
  case "path": __constructor = __library.StringSchema; break;
  default: throw new Error(`Unexpected type ${__info.type}`);
 }
 if (__info.exception) {
  __parameters.validate = (__value, __schema, __utils) => __info.exception(__value) || __schema.validate(__value, __utils);
 } else {
  __parameters.validate = (__value, __schema, __utils) => __value === undefined || __schema.validate(__value, __utils);
 }
 if (__info.redirect) {
  __handlers.redirect = (__value) => !__value ? undefined : {to: typeof __info.redirect === "string" ? __info.redirect : {key: __info.redirect.option, value: __info.redirect.value}};
 }
 if (__info.deprecated) {__handlers.deprecated = true;}
 if (isCLI && !__info.array) {
  const __original = __parameters.preprocess || ((__identity) => __identity);
  __parameters.preprocess = (__value, __schema, __utils) => __schema.preprocess(__original(Array.isArray(__value) ? __value.at(-1) : __value), __utils);
 }
 return __info.array
  ? __library.ArraySchema.create({...(isCLI ? {preprocess: (__arrayValue) => (Array.isArray(__arrayValue) ? __arrayValue : [__arrayValue])} : {}), ...__handlers, valueSchema: __constructor.create(__parameters)})
  : __constructor.create({...__parameters, ...__handlers});
}'''

VALUE_NORMALIZER = '''function normalize(__options, __infos, {logger = false, isCLI = false, passThrough = false, FlagSchema, descriptor} = {}) {
 if (isCLI) {
  if (!FlagSchema) {throw new Error("'FlagSchema' option is required.");}
  if (!descriptor) {throw new Error("'descriptor' option is required.");}
 } else {descriptor = __library.apiDescriptor;}
 const __unknown = !passThrough
  ? (__key, __value, __settings) => {
   const {_, ...schemas} = __settings.schemas;
   return __library.levenUnknownHandler(__key, __value, {...__settings, schemas});
  }
  : Array.isArray(passThrough)
   ? (__key, __value) => !passThrough.includes(__key) ? undefined : {[__key]: __value}
   : (__key, __value) => ({[__key]: __value});
 const __schemas = __create(__infos, {isCLI, FlagSchema});
 const __normalizer = new __library.Normalizer(__schemas, {logger, unknown: __unknown, descriptor});
 const __suppress = logger !== false;
 if (__suppress && __warned) {__normalizer._hasDeprecationWarned = __warned;}
 const __normalized = __normalizer.normalize(__options);
 if (__suppress) {__warned = __normalizer._hasDeprecationWarned;}
 return __normalized;
}'''
