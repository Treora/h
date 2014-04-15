// Generated by CoffeeScript 1.6.3
/*
** Annotator 1.2.6-dev-89aa294
** https://github.com/okfn/annotator/
**
** Copyright 2012 Aron Carroll, Rufus Pollock, and Nick Stenning.
** Dual licensed under the MIT and GPLv3 licenses.
** https://github.com/okfn/annotator/blob/master/LICENSE
**
** Built at: 2014-04-15 06:22:51Z
*/



/*
//
*/

// Generated by CoffeeScript 1.6.3
(function() {
  var TextPositionAnchor, _ref,
    __hasProp = {}.hasOwnProperty,
    __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    __bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; };

  TextPositionAnchor = (function(_super) {
    __extends(TextPositionAnchor, _super);

    TextPositionAnchor.Annotator = Annotator;

    function TextPositionAnchor(annotator, annotation, target, start, end, startPage, endPage, quote, diffHTML, diffCaseOnly) {
      this.start = start;
      this.end = end;
      TextPositionAnchor.__super__.constructor.call(this, annotator, annotation, target, startPage, endPage, quote, diffHTML, diffCaseOnly);
      if (this.start == null) {
        throw new Error("start is required!");
      }
      if (this.end == null) {
        throw new Error("end is required!");
      }
      this.Annotator = TextPositionAnchor.Annotator;
      this.$ = this.Annotator.$;
    }

    TextPositionAnchor.prototype._createHighlight = function(page) {
      var dfd,
        _this = this;
      dfd = this.$.Deferred();
      this.annotator.domMapper.prepare("highlighting").then(function(s) {
        var browserRange, e2, error, hl, mappings, normedRange, realRange;
        try {
          mappings = s.getMappingsForCharRange(_this.start, _this.end, [page]);
          realRange = mappings.sections[page].realRange;
          browserRange = new _this.Annotator.Range.BrowserRange(realRange);
          normedRange = browserRange.normalize(_this.annotator.wrapper[0]);
          hl = new _this.Annotator.TextHighlight(_this, page, normedRange);
          return dfd.resolve(hl);
        } catch (_error) {
          error = _error;
          try {
            return dfd.reject({
              message: "Cought exception",
              error: error
            });
          } catch (_error) {
            e2 = _error;
            return console.log("WTF", e2.stack);
          }
        }
      });
      return dfd.promise();
    };

    TextPositionAnchor.prototype._verify = function(reason, data) {
      var dfd,
        _this = this;
      dfd = this.$.Deferred();
      if (reason !== "corpus change") {
        dfd.resolve(true);
        return dfd.promise();
      }
      this.annotator.domMapper.prepare("verifying an anchor").then(function(s) {
        var content, corpus, currentQuote;
        corpus = s.getCorpus();
        content = corpus.slice(anchor.start, anchor.end).trim();
        currentQuote = _this.annotator.normalizeString(content);
        return dfd.resolve(currentQuote === anchor.quote);
      });
      return dfd.promise();
    };

    return TextPositionAnchor;

  })(Annotator.Anchor);

  Annotator.Plugin.TextPosition = (function(_super) {
    __extends(TextPosition, _super);

    function TextPosition() {
      this._createFromPositionSelector = __bind(this._createFromPositionSelector, this);
      this._getTextPositionSelector = __bind(this._getTextPositionSelector, this);
      _ref = TextPosition.__super__.constructor.apply(this, arguments);
      return _ref;
    }

    TextPosition.prototype.pluginInit = function() {
      this.Annotator = Annotator;
      this.$ = Annotator.$;
      if (!this.annotator.plugins.DomTextMapper) {
        throw new Error("The TextPosition Annotator plugin requires the DomTextMapper plugin.");
      }
      this.annotator.selectorCreators.push({
        name: "TextPositionSelector",
        describe: this._getTextPositionSelector
      });
      this.annotator.anchoringStrategies.push({
        name: "position",
        create: this._createFromPositionSelector,
        verify: this.verifyTextAnchor
      });
      return this.Annotator.TextPositionAnchor = TextPositionAnchor;
    };

    TextPosition.prototype._getTextPositionSelector = function(selection) {
      var dfd, endOffset, startOffset, state;
      dfd = this.$.Deferred();
      if (selection.type !== "text range") {
        dfd.reject("I can only describe text ranges");
        return dfd.promise();
      }
      state = selection.data.dtmState;
      startOffset = (state.getStartInfoForNode(selection.range.start)).start;
      endOffset = (state.getEndInfoForNode(selection.range.end)).end;
      dfd.resolve([
        {
          type: "TextPositionSelector",
          start: startOffset,
          end: endOffset
        }
      ]);
      return dfd.promise();
    };

    TextPosition.prototype._createFromPositionSelector = function(annotation, target) {
      var dfd, selector,
        _this = this;
      dfd = this.$.Deferred();
      if (!this.annotator.plugins.DomTextMapper) {
        dfd.reject("DTM is not present");
        return dfd.promise();
      }
      selector = this.annotator.findSelector(target.selector, "TextPositionSelector");
      if (!selector) {
        dfd.reject("no TextPositionSelector found", true);
        return dfd.promise();
      }
      this.annotator.domMapper.prepare("anchoring").then(function(s) {
        var content, currentQuote, savedQuote;
        content = s.getCorpus().slice(selector.start, selector.end).trim();
        currentQuote = _this.annotator.normalizeString(content);
        savedQuote = _this.annotator.getQuoteForTarget(target);
        if ((savedQuote != null) && currentQuote !== savedQuote) {
          dfd.reject("the saved quote doesn't match");
          return dfd.promise();
        }
        return dfd.resolve(new TextPositionAnchor(_this.annotator, annotation, target, selector.start, selector.end, s.getPageIndexForPos(selector.start), s.getPageIndexForPos(selector.end), currentQuote));
      });
      return dfd.promise();
    };

    return TextPosition;

  })(Annotator.Plugin);

}).call(this);

//
//@ sourceMappingURL=annotator.textposition.map