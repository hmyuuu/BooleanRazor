# Source-to-standalone commit map

The standalone `main` history was produced from the
`tracks/qcs/solutions/hmyuuu` subtree. Git rewrote commit IDs because each
standalone commit contains only that subtree. Subjects and order are preserved.
Plan-only source commits have no standalone equivalent.

| Source quantum.harness commit | Standalone BooleanRazor commit | Subject |
| --- | --- | --- |
| `61df571e77c2cb4eb5ebddf5842bbd88ea72de77` | `65dc09ee37e79284b98594e5089fcc04048a5f98` | feat(qcs): pin Occam Circuit v1 contract |
| `018973e76b7b455c93d1858463688b7fb55462ba` | `ed82026d1328f08601fc0496cfb5648a4385c084` | test(qcs): assert Occam v1 commitments |
| `874595be6f4b529f63ace739124b047990142921` | `4f01dd87a0e6aab5542359cfa87cb492524e8aa4` | feat(qcs): add strict Occam truth tables |
| `af8b55fef8d0c0336bc2d1c8b0ea2ce620cff337` | `58ad1bac2305ea96d40b94e5c77992da9964b7c1` | fix(qcs): validate observed truth-table labels |
| `d2a5cd4bffc8f09c8aec90fb883f4317829453b4` | `05950c409983121c537110c02be51c9654d86b77` | feat(qcs): add challenge-native XAG netlists |
| `bd617a361e0799319380ba2e84d8706b972defcb` | `cb3206db557ebd64e9fcca70027ea69519a4a122` | fix(qcs): reject foreign XAG literals |
| `3741f4c4b91db7d1937db4d6398ab5a572183a34` | `787e24a95293842453da6e0287a3ad32c268744a` | feat(qcs): synthesize exact v1 arithmetic circuits |
| `b76e52bb582cd8bb468dbdd8dd37f5ea822f71ba` | `3ef38bba029422fc556efa136e07e640be63aebc` | fix(qcs): reject overflowing arithmetic widths |
| `08225d487ea97ac017d355e298c2b0220366cf4c` | `7ca8fb44d818eab062e80c2cd716df68d36c172f` | feat(qcs): generate commitment-matching v1 submission |
| `39b4bc7df8457a9e48cc4bd05042b3e41f5c8f74` | `1c790832fd4569166ff9d7038fdd3b5a92dbabaa` | fix(qcs): harden v1 artifact transaction |
| `5c2762790c90b9ee4d85083ecd015ec20941a692` | `b58b262281e5675ec77c076871fe5d8c573b4df4` | feat(qcs): add shared complemented ROBDD synthesis |
| `c0074df516aebedf682035ac8b867482194f139d` | `c1189d8b23850551b6fb1207740b54175ad5b4fc` | fix(qcs): validate bit-parallel XAG outputs |
| `173e21c8f0d0b5979174ffc58911e19ccf2a1a1a` | `59c2cc8ef3f7e3f7658fc3cd6900b1eee3753a1d` | test(qcs): cross-check ROBDDs with OxiDD |
| `986d37bc8d0a8c16933975bfcd5e89c38cff7c7c` | `54e1f6858f0562d80eed51998ad689baec69f3e4` | feat(qcs): search BDD orders by XAG score |
| `aeb538ccb323350ffb32ef9ea288b7af56fd031e` | `50b4adbbac06462ee9b24047d387d3dce9d77b44` | feat(qcs): freeze blind baseline protocol |
| `3daa172b56c00743ed06b30ac6b18716fbfad1b2` | `2f36e101e0f0ee731f340d01d4fe4d0196a3c3da` | fix(qcs): harden blind research gate |
| `8f31f9549e5c028429db7d3b4dc4e5fac33fc477` | `38c00ed2557cf38ef3203fd5ff0fde9c4bf5737d` | data(qcs): commit sealed blind benchmark |
| `749bb60b464558f85880502a27eed7b421151ba0` | `a824e5af9fcfe41754e8b924696d1582e3f2751e` | feat(qcs): add auditable autoresearch runner |
| `24dbef434dc69303032415d10640eaebfef075b4` | `93ffdd29b54998c95720d0b226d6b58deb8cb216` | fix(qcs): harden autoresearch evidence paths |
| `735ec28cf9474e51cfb14b758a614324e15216c8` | `336f4782a1cab3b7586136405e32aaf3aa6ec2cc` | fix(qcs): preserve terminal runner evidence |
