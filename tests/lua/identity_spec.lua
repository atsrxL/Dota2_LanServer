local Identity=require('lan.identity')
local entities={[100]={},[101]={},[999]={}}
local res={GetPlayer=function(self,pid) if pid==0 then return entities[100] elseif pid==1 then return entities[101] end end}
local lookup=function(i)return entities[i]end
assert(Identity.resolve(100,res,lookup)==0)
assert(Identity.resolve(101,res,lookup)==1)
assert(Identity.resolve(999,res,lookup)==nil)
assert(Identity.resolve('100',res,lookup)==nil)
assert(Identity.resolve(-1,res,lookup)==nil)
assert(Identity.resolve(1.5,res,lookup)==nil)
assert(Identity.resolve(100,res,function()error('invalid')end)==nil)
print('identity_spec: event source mapped; payload identity cannot grant authority PASS')
